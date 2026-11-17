from __future__ import annotations

from conftest import make_repo, outcome_of, status_of
from repo_doctor.checks.links import resolve_link
from repo_doctor.markdown import anchors, headings, links, slugify
from repo_doctor.model import Status


def test_resolve_link():
    assert resolve_link("docs/a.md", "../README.md") == ("README.md", "")
    assert resolve_link("docs/a.md", "b.md#Intro") == ("docs/b.md", "Intro")
    assert resolve_link("docs/a.md", "/LICENSE") == ("LICENSE", "")
    assert resolve_link("a.md", "#top") == ("a.md", "top")
    assert resolve_link("a.md", "my%20file.md?raw=1") == ("my file.md", "")


def test_broken_and_valid_links(tmp_path):
    readme = """\
# Title

[ok](docs/guide.md) [dir](docs/) [img](img/logo.png "Logo") [root](/LICENSE)
[broken](docs/missing.md) [web](https://example.com) [mail](mailto:team)
[anchor](#title) [bad anchor](#nope) [other](docs/guide.md#setup-steps)
[ref]: docs/also-missing.md
<a href="docs/guide.md">html</a> <img src="img/none.png">

```
[in code](nowhere.md)
```

`[inline](nowhere.md)`
"""
    repo = make_repo(
        tmp_path,
        {
            "README.md": readme,
            "docs/guide.md": "# Guide\n\n## Setup steps\n",
            "img/logo.png": b"\x89PNG",
            "LICENSE": "x",
        },
    )
    outcome = outcome_of(repo, "RD016")
    assert outcome.status == Status.FAIL
    broken = [d.split(" -> ")[1] for d in outcome.details]
    assert broken == ["docs/missing.md", "#nope", "docs/also-missing.md", "img/none.png"]


def test_links_ignore_config_and_skip(tmp_path):
    repo = make_repo(
        tmp_path / "a",
        {"docs/gen/api.md": "[x](missing.md)\n", ".repo-doctor.toml": '[links]\nignore = ["docs/gen/**"]\n'},
    )
    assert status_of(repo, "RD016") == Status.SKIP
    assert status_of(make_repo(tmp_path / "b", {"a.txt": "x"}), "RD016") == Status.SKIP
    ok = make_repo(tmp_path / "c", {"README.md": "[up](../outside.md) [tpl]({{ url }})\n"})
    assert status_of(ok, "RD016") == Status.PASS


def test_headings_and_anchors():
    text = '# Hello World\n\nSetext\n======\n\n## Hello World\n\n## `code` & More!\n<a name="custom"></a>\n'
    assert headings(text) == ["Hello World", "Setext", "Hello World", "code & More!"]
    assert anchors(text) == {"hello-world", "setext", "hello-world-1", "code--more", "custom"}
    assert slugify("Ünïcode Title") == "ünïcode-title"


def test_links_parser_skips_code():
    text = "    [indented](code.md)\n~~~\n[x](y.md)\n~~~\n[real](z.md)\n"
    assert [link.target for link in links(text)] == ["z.md"]
