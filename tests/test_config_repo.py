from __future__ import annotations

import pytest

from conftest import REPO_ROOT, init_git, make_repo
from repo_doctor.config import Config, ConfigError, load_config
from repo_doctor.engine import run_checks
from repo_doctor.repo import Repo, matches_any


def test_defaults(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.large_file_mb == 5 and cfg.fail_under is None and cfg.remote is True
    assert cfg.readme_sections == ["install", "usage", "license", "contributing"]


def test_load_from_dotfile_and_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.repo-doctor]\nlarge_file_mb = 9\n")
    assert load_config(tmp_path).large_file_mb == 9
    (tmp_path / ".repo-doctor.toml").write_text("large_file_mb = 3\n")
    cfg = load_config(tmp_path)
    assert cfg.large_file_mb == 3 and cfg.source == ".repo-doctor.toml"


def test_broken_pyproject_is_ignored(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[broken")
    assert load_config(tmp_path) == Config()


@pytest.mark.parametrize(
    "data",
    [
        {"unknown": 1},
        {"disable": "RD001"},
        {"large_file_mb": 0},
        {"fail_under": 101},
        {"readme_sections": ["faq"]},
        {"secrets": []},
        {"links": "x"},
        {"remote": "yes"},
        {"secrets": {"allow_paths": [1]}},
    ],
)
def test_invalid_config(data):
    with pytest.raises(ConfigError):
        Config.from_dict(data, "test")


def test_invalid_toml(tmp_path):
    (tmp_path / ".repo-doctor.toml").write_text("disable = [")
    with pytest.raises(ConfigError, match="not valid TOML"):
        load_config(tmp_path)


def test_walk_skips_dependency_folders(tmp_path):
    repo = make_repo(tmp_path, {"a.py": "", "node_modules/x/index.js": "", ".venv/lib.py": "", "sub/b.py": ""})
    assert repo.files == ["a.py", "sub/b.py"]
    assert repo.tracked is None and not repo.is_git


def test_git_file_listing_respects_gitignore(tmp_path):
    root = tmp_path / "g"
    make_repo(root, {".gitignore": "ignored.txt\n", "a.py": "", "ignored.txt": ""})
    init_git(root)
    (root / "new.py").write_text("")
    repo = Repo(root)
    assert repo.is_git
    assert set(repo.files) == {".gitignore", "a.py", "new.py"}
    assert repo.tracked == {".gitignore", "a.py"}
    assert repo.is_tracked("a.py") and not repo.is_tracked("new.py")


def test_subfolder_of_git_repo_is_treated_as_folder(tmp_path):
    root = tmp_path / "g"
    make_repo(root, {"sub/a.py": ""})
    init_git(root)
    assert not Repo(root / "sub").is_git


def test_find_is_case_insensitive(tmp_path):
    repo = make_repo(tmp_path, {"License.MD": "x", "docs/Contributing.md": "y"})
    assert repo.find(["LICENSE.md"]) == "License.MD"
    assert repo.find_doc(("CONTRIBUTING",)) == "docs/Contributing.md"
    assert repo.find(["nope"]) is None


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ({"pyproject.toml": ""}, ["python"]),
        ({"package.json": "{}", "tsconfig.json": "{}"}, ["javascript", "typescript"]),
        ({"a.ts": "", "b.ts": "", "c.ts": "", "package.json": "{}"}, ["javascript", "typescript"]),
        ({"composer.json": "{}"}, ["php"]),
        ({"go.mod": ""}, ["go"]),
        ({"Cargo.toml": ""}, ["rust"]),
        ({"Dockerfile": ""}, ["docker"]),
        ({"deploy/Dockerfile.prod": ""}, ["docker"]),
        ({"one.py": ""}, []),
        ({"x.py": "", "y.py": "", "z.py": ""}, ["python"]),
    ],
)
def test_language_detection(tmp_path, files, expected):
    assert sorted(make_repo(tmp_path, files).languages) == sorted(expected)


def test_project_and_author_names(tmp_path):
    repo = make_repo(
        tmp_path / "a",
        {"package.json": '{"name": "pkg", "author": "Jane Roe <jane@example.org> (https://x)"}'},
    )
    assert repo.project_name == "pkg"
    if not repo.git or not repo._git("config", "--get", "user.name"):
        assert repo.author_name == "Jane Roe"
    py = make_repo(tmp_path / "b", {"pyproject.toml": '[project]\nname="pyname"\nauthors=[{name="Ann"}]\n'})
    assert py.project_name == "pyname"
    assert make_repo(tmp_path / "plain").project_name == "plain"


def test_matches_any():
    assert matches_any("tests/fixtures/a.env", ["tests/fixtures/**"])
    assert matches_any("a/b.min.js", ["*.min.js"])
    assert not matches_any("src/a.py", ["tests/**"])


def test_not_a_directory(tmp_path):
    with pytest.raises(NotADirectoryError):
        Repo(tmp_path / "missing")


def test_self_check_offline():
    """repo-doctor must pass its own checks."""

    report = run_checks(Repo(REPO_ROOT), remote=False)
    problems = [(r.check.id, r.outcome.message) for r in report.results if r.counts_against]
    assert report.score >= 95, problems
