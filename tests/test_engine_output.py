from __future__ import annotations

import json

import pytest

from conftest import make_repo
from repo_doctor import model
from repo_doctor.engine import Report, grade_for, run_checks, select_checks
from repo_doctor.model import CheckInfo, Location, Outcome, Result, Severity, Status, all_checks, resolve
from repo_doctor.output import render, render_markdown, render_sarif, render_text


def test_registry_is_consistent():
    infos = all_checks()
    assert len(infos) >= 25
    assert len({i.id for i in infos}) == len(infos)
    assert len({i.slug for i in infos}) == len(infos)
    for info in infos:
        assert info.id.startswith("RD") and info.explanation and info.fix_hint
        assert info.title[0].isupper() or info.title[0] == "."


def test_resolve_by_id_slug_and_fixer():
    assert [i.id for i in resolve(["rd001"])] == ["RD001"]
    assert [i.id for i in resolve(["secrets"])] == ["RD015"]
    assert {i.id for i in resolve(["gitignore"])} == {"RD010", "RD011"}
    with pytest.raises(KeyError):
        resolve(["nope"])


def test_duplicate_registration_rejected():
    with pytest.raises(ValueError):
        model.check("RD001", "x-dup", "t", Severity.LOW, "docs", "e", "f")(lambda repo: None)
    with pytest.raises(ValueError):
        model.check("RD999", "readme", "t", Severity.LOW, "docs", "e", "f")(lambda repo: None)


def test_healthy_repo_scores_100(healthy):
    report = run_checks(healthy, remote=False)
    assert report.score == 100, [(r.check.id, r.outcome.message) for r in report.results if r.counts_against]
    assert report.grade == "A"


def test_empty_repo_scores_low(tmp_path):
    report = run_checks(make_repo(tmp_path), remote=False)
    assert report.score < 20
    assert report.grade == "F"
    assert report.failing_at_or_above(Severity.HIGH)


@pytest.mark.parametrize(
    ("score", "grade"), [(100, "A"), (90, "A"), (89, "B"), (80, "B"), (70, "C"), (60, "D"), (59, "F"), (0, "F")]
)
def test_grades(score, grade):
    assert grade_for(score) == grade


def _info(severity=Severity.HIGH, id="RDX1"):
    return CheckInfo(id, id.lower(), "Title", severity, "docs", "e", "f")


def test_score_math(tmp_path):
    repo = make_repo(tmp_path)
    report = Report(repo)
    report.results = [
        Result(_info(Severity.HIGH, "A"), Outcome(Status.PASS, "")),
        Result(_info(Severity.MEDIUM, "B"), Outcome(Status.WARN, "")),
        Result(_info(Severity.LOW, "C"), Outcome(Status.FAIL, "")),
        Result(_info(Severity.HIGH, "D"), Outcome(Status.SKIP, "")),
        Result(_info(Severity.HIGH, "E"), Outcome(Status.ERROR, "")),
    ]
    # earned 10 + 2.5 of 17
    assert report.score == round(100 * 12.5 / 17)
    assert Report(repo).score == 100


def test_disable_only_skip(tmp_path):
    repo = make_repo(tmp_path, {".repo-doctor.toml": 'disable = ["RD008", "readme-badges", "unknown-check"]\n'})
    ids = {i.id for i in select_checks(repo)}
    assert "RD008" not in ids and "RD003" not in ids and "RD001" in ids
    assert [i.id for i in select_checks(repo, only=["RD001", "RD008"])] == ["RD001"]
    assert "RD015" not in {i.id for i in select_checks(repo, skip=["secrets"])}


def test_crashing_check_reports_error(tmp_path, monkeypatch):
    info, _ = model.REGISTRY["RD012"]

    def boom(repo):
        raise RuntimeError("kaput")

    monkeypatch.setitem(model.REGISTRY, "RD012", (info, boom))
    result = run_checks(make_repo(tmp_path), only=["RD012"]).results[0]
    assert result.status == Status.ERROR and "kaput" in result.outcome.message


def test_text_output(tmp_path):
    report = run_checks(make_repo(tmp_path, {"Dockerfile": "FROM x:latest\n"}), remote=False)
    text = render_text(report)
    assert "Score:" in text and "FAIL  RD004" in text and "auto-fix: repo-doctor fix --only license" in text
    assert "SKIP" not in text
    verbose = render_text(report, verbose=True, color=True)
    assert "SKIP" in verbose and "\033[31m" in verbose


def test_json_output(healthy):
    data = json.loads(render(run_checks(healthy, remote=False), "json"))
    assert data["score"] == 100 and data["grade"] == "A" and data["languages"] == ["Python"]
    assert {"id", "status", "severity", "fix_hint", "fixable"} <= set(data["results"][0])


def test_markdown_output(tmp_path):
    report = run_checks(make_repo(tmp_path), remote=False)
    md = render_markdown(report)
    assert md.startswith("## Repository health:")
    assert "| ❌ | `RD004`" in md
    assert "### How to fix" in md and "<details><summary>Skipped checks</summary>" in md


def test_sarif_output(tmp_path):
    repo = make_repo(tmp_path, {"a.txt": "k=" + "AKIA" + "Z" * 16 + "\n"})
    sarif = json.loads(render_sarif(run_checks(repo, remote=False)))
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    rule_ids = [r["id"] for r in run["tool"]["driver"]["rules"]]
    assert rule_ids == sorted(rule_ids) and "RD015" in rule_ids
    secret = next(r for r in run["results"] if r["ruleId"] == "RD015")
    assert secret["level"] == "error"
    assert secret["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "a.txt"
    assert secret["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    assert rule_ids[secret["ruleIndex"]] == "RD015"
    readme = next(r for r in run["results"] if r["ruleId"] == "RD001")
    assert readme["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == "."
    security_rule = run["tool"]["driver"]["rules"][rule_ids.index("RD015")]
    assert security_rule["properties"]["security-severity"] == "8.0"


def test_location_str():
    assert str(Location("a", 3)) == "a:3" and str(Location("a")) == "a"
