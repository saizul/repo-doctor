from __future__ import annotations

import json

import pytest

from conftest import REPO_ROOT, make_repo
from repo_doctor import __version__
from repo_doctor.cli import checks_markdown, main


def run(capsys, *args):
    code = main([str(a) for a in args])
    out, err = capsys.readouterr()
    return code, out, err


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0 and __version__ in capsys.readouterr().out


def test_help_without_command(capsys):
    code, out, _ = run(capsys)
    assert code == 2 and "usage" in out


def test_check_text_default_exit_zero(capsys, tmp_path):
    code, out, _ = run(capsys, "check", make_repo(tmp_path).root)
    assert code == 0 and "Grade: F" in out


def test_fail_under(capsys, tmp_path, healthy):
    code, _, err = run(capsys, "check", make_repo(tmp_path / "e").root, "--fail-under", "50")
    assert code == 1 and "below 50" in err
    assert run(capsys, "check", healthy.root, "--fail-under", "100")[0] == 0


def test_fail_under_from_config(capsys, tmp_path):
    repo = make_repo(tmp_path, {".repo-doctor.toml": "fail_under = 90\n"})
    assert run(capsys, "check", repo.root)[0] == 1


def test_fail_on(capsys, tmp_path):
    repo = make_repo(tmp_path, {"README.md": "word " * 50, "LICENSE": "SPDX-License-Identifier: MIT\n"})
    code, _, err = run(capsys, "check", repo.root, "--fail-on", "high", "--only", "RD001,RD004")
    assert code == 0
    code, _, err = run(capsys, "check", repo.root, "--fail-on", "low", "--only", "RD008")
    assert code == 1 and "severity low" in err


def test_formats_and_files(capsys, tmp_path, healthy):
    out_dir = tmp_path / "out"
    code, out, _ = run(
        capsys,
        "check",
        healthy.root,
        "-f",
        "json",
        "--sarif-file",
        out_dir / "r.sarif",
        "--markdown-file",
        out_dir / "r.md",
        "--json-file",
        out_dir / "r.json",
    )
    assert code == 0
    assert json.loads(out)["score"] == 100
    assert json.loads((out_dir / "r.sarif").read_text())["version"] == "2.1.0"
    assert (out_dir / "r.md").read_text().startswith("## Repository health: 100/100")
    assert json.loads((out_dir / "r.json").read_text())["grade"] == "A"
    code, out, _ = run(capsys, "check", healthy.root, "-f", "markdown", "-o", out_dir / "report.md")
    assert out == "" and (out_dir / "report.md").exists()
    assert json.loads(run(capsys, "check", healthy.root, "-f", "sarif")[1])["runs"]


def test_github_summary_and_outputs(capsys, tmp_path, monkeypatch, healthy):
    summary = tmp_path / "summary.md"
    outputs = tmp_path / "outputs.txt"
    summary.write_text("previous\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    assert run(capsys, "check", healthy.root, "--github-summary")[0] == 0
    text = summary.read_text()
    assert text.startswith("previous\n") and "## Repository health" in text
    assert outputs.read_text() == "score=100\ngrade=A\n"


def test_only_skip_unknown(capsys, healthy):
    code, out, _ = run(capsys, "check", healthy.root, "--only", "RD001", "--skip", "RD002")
    assert code == 0 and "RD001" in out and "RD004" not in out
    code, _, err = run(capsys, "check", healthy.root, "--only", "RD999")
    assert code == 2 and "unknown check" in err


def test_bad_path_and_bad_config(capsys, tmp_path):
    code, _, err = run(capsys, "check", tmp_path / "missing")
    assert code == 2 and "not a directory" in err
    cfg_root = tmp_path / "cfg"
    cfg_root.mkdir()
    (cfg_root / ".repo-doctor.toml").write_text("large_file_mb = -1\n")
    code, _, err = run(capsys, "check", cfg_root)
    assert code == 2 and "large_file_mb" in err


def test_fix_command(capsys, tmp_path):
    root = make_repo(tmp_path, {"package.json": "{}"}).root
    code, out, _ = run(capsys, "fix", root, "--dry-run")
    assert code == 0 and "[dry-run] create" in out and not (root / "LICENSE").exists()
    code, out, _ = run(capsys, "fix", root, "--only", "license,security", "--license", "Apache-2.0", "--author", "A B")
    assert code == 0 and "create    LICENSE" in out and "Score after fixing" in out
    assert "Apache License" in (root / "LICENSE").read_text()
    code, out, _ = run(capsys, "fix", root, "--only", "license")
    assert "skip" in out and "--force" in out
    code, _, err = run(capsys, "fix", root, "--only", "bogus")
    assert code == 2 and "unknown fixer" in err


def test_fix_nothing_to_do(capsys, healthy):
    code, out, _ = run(capsys, "fix", healthy.root)
    assert code == 0 and "Nothing to fix" in out


def test_checks_command(capsys):
    code, out, _ = run(capsys, "checks")
    assert code == 0 and "RD015" in out and "remote" in out
    data = json.loads(run(capsys, "checks", "-f", "json")[1])
    assert data[0]["id"] == "RD001"
    assert '<a id="rd015"></a>' in run(capsys, "checks", "-f", "markdown")[1]


def test_docs_checks_md_is_up_to_date():
    path = REPO_ROOT / "docs" / "checks.md"
    assert path.read_text(encoding="utf-8").strip() == checks_markdown().strip(), (
        "docs/checks.md is outdated: run `repo-doctor checks -f markdown > docs/checks.md`"
    )
