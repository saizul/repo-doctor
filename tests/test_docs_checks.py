from __future__ import annotations

import pytest

from conftest import MIT_TEXT, REPO_ROOT, make_repo, outcome_of, status_of
from repo_doctor.licenses import copyright_line, detect_spdx
from repo_doctor.model import Status

APACHE = (REPO_ROOT / "src/repo_doctor/templates/licenses/Apache-2.0.txt").read_text()


def test_healthy_repo_passes_docs_checks(healthy):
    for check_id in ("RD001", "RD002", "RD003", "RD004", "RD005", "RD006", "RD007", "RD008"):
        assert status_of(healthy, check_id) == Status.PASS, check_id


def test_readme_missing_and_short(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD001") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {"README.md": "# x\n"}), "RD001") == Status.WARN


def test_readme_found_in_docs_and_rst(tmp_path):
    words = "word " * 40
    assert status_of(make_repo(tmp_path / "a", {"docs/README.md": words}), "RD001") == Status.PASS
    assert status_of(make_repo(tmp_path / "b", {"README.rst": words}), "RD001") == Status.PASS
    assert status_of(make_repo(tmp_path / "c", {"readme.MD": words}), "RD001") == Status.PASS


@pytest.mark.parametrize(
    ("readme", "status"),
    [
        ("## Getting started\n## Examples\n## License\n## Contributing\n", Status.PASS),
        ("## Install\n## Usage\n## Licence\n", Status.WARN),
        ("Title\n=====\n\nInstallation\n------------\n", Status.FAIL),
        ("```\n## Usage\n```\n## Install\n", Status.FAIL),
    ],
)
def test_readme_sections(tmp_path, readme, status):
    assert status_of(make_repo(tmp_path, {"README.md": readme}), "RD002") == status


def test_readme_sections_respects_config(tmp_path):
    repo = make_repo(tmp_path, {"README.md": "## Usage\n", ".repo-doctor.toml": 'readme_sections = ["usage"]\n'})
    assert status_of(repo, "RD002") == Status.PASS


def test_readme_badges(tmp_path):
    with_badge = "[![CI](https://img.shields.io/badge/ci-passing-green)](x)\n"
    html_badge = '<img src="https://github.com/o/r/actions/workflows/ci.yml/badge.svg">\n'
    assert status_of(make_repo(tmp_path / "a", {"README.md": with_badge}), "RD003") == Status.PASS
    assert status_of(make_repo(tmp_path / "b", {"README.md": html_badge}), "RD003") == Status.PASS
    assert status_of(make_repo(tmp_path / "c", {"README.md": "no badges\n"}), "RD003") == Status.FAIL
    assert status_of(make_repo(tmp_path / "d"), "RD003") == Status.FAIL
    assert status_of(make_repo(tmp_path / "e"), "RD002") == Status.FAIL


def test_license_detection(tmp_path):
    mit = MIT_TEXT.replace("@@YEAR@@", "2026").replace("@@AUTHOR@@", "Jane Doe")
    outcome = outcome_of(make_repo(tmp_path / "a", {"LICENSE": mit}), "RD004")
    assert outcome.status == Status.PASS and "MIT" in outcome.message
    assert outcome.details == ["Copyright (c) 2026 Jane Doe"]
    outcome = outcome_of(make_repo(tmp_path / "b", {"LICENSE.txt": APACHE}), "RD004")
    assert "Apache-2.0" in outcome.message


def test_license_problems(tmp_path):
    assert status_of(make_repo(tmp_path / "a"), "RD004") == Status.FAIL
    assert status_of(make_repo(tmp_path / "b", {"LICENSE": "All rights reserved.\n"}), "RD004") == Status.WARN
    placeholder = MIT_TEXT.replace("@@YEAR@@", "[year]").replace("@@AUTHOR@@", "[fullname]")
    assert status_of(make_repo(tmp_path / "c", {"LICENSE": placeholder}), "RD004") == Status.WARN
    assert status_of(make_repo(tmp_path / "d", {"COPYING": "SPDX-License-Identifier: GPL-3.0-only\n"}), "RD004") == (
        Status.WARN
    )
    assert status_of(
        make_repo(tmp_path / "e", {"LICENSE": "SPDX-License-Identifier: MIT OR Apache-2.0\n"}), "RD004"
    ) == (Status.PASS)


@pytest.mark.parametrize(
    ("text", "spdx"),
    [
        ("GNU AFFERO GENERAL PUBLIC LICENSE Version 3, 19 November 2007", "AGPL-3.0"),
        ("GNU GENERAL PUBLIC LICENSE\n Version 3, 29 June 2007", "GPL-3.0"),
        ("GNU GENERAL PUBLIC LICENSE Version 2, June 1991", "GPL-2.0"),
        ("GNU LESSER GENERAL PUBLIC LICENSE Version 2.1, February 1999", "LGPL-2.1"),
        ("Mozilla Public License Version 2.0", "MPL-2.0"),
        ("This is free and unencumbered software released into the public domain.", "Unlicense"),
        (
            "Redistribution and use in source and binary forms, with or without modification... "
            "Neither the name of the copyright holder",
            "BSD-3-Clause",
        ),
        ("Redistribution and use in source and binary forms, with or without modification", "BSD-2-Clause"),
        (
            "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee "
            "is hereby granted, provided that the above copyright notice and this permission notice appear",
            "ISC",
        ),
        (
            "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee "
            "is hereby granted.",
            "0BSD",
        ),
        ("Boost Software License - Version 1.0", "BSL-1.0"),
        ("", None),
        ("Proprietary. Do not copy.", None),
    ],
)
def test_detect_spdx(text, spdx):
    assert detect_spdx(text) == spdx


def test_copyright_line():
    assert copyright_line("x\nCopyright 2020 A\n") == "Copyright 2020 A"
    assert copyright_line("© nobody") is None


@pytest.mark.parametrize(
    ("check_id", "path"),
    [
        ("RD005", ".github/CONTRIBUTING.md"),
        ("RD006", "docs/CODE_OF_CONDUCT.md"),
        ("RD007", ".github/SECURITY.md"),
        ("RD008", "CHANGES.rst"),
        ("RD008", "HISTORY.md"),
    ],
)
def test_community_files_in_alternative_locations(tmp_path, check_id, path):
    repo = make_repo(tmp_path, {path: "A reasonably long document with enough content to count as real.\n"})
    assert status_of(repo, check_id) == Status.PASS


def test_nearly_empty_community_file_warns(tmp_path):
    assert status_of(make_repo(tmp_path, {"SECURITY.md": "todo\n"}), "RD007") == Status.WARN
    assert status_of(make_repo(tmp_path / "x"), "RD005") == Status.FAIL
