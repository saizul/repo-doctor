"""Minimal Markdown helpers: headings, links and GitHub-style heading anchors."""

from __future__ import annotations

import re
from dataclasses import dataclass

_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_ATX_RE = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
_SETEXT_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
_INLINE_CODE_RE = re.compile(r"(`+)(?:(?!\1).)+?\1")
_INLINE_LINK_RE = re.compile(r"!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'(][^)]*[\"')])?\s*\)")
_REF_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+[\"'(].*)?$")
_HTML_LINK_RE = re.compile(r"<(?:a|img)\s[^>]*?(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)


@dataclass(frozen=True)
class Link:
    target: str
    line: int


def _code_free_lines(text: str):
    """Yield ``(lineno, line)`` for lines outside fenced and indented code blocks."""

    fence: str | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = _FENCE_RE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker[0] * len(marker)
                continue
            if marker.startswith(fence):
                fence = None
                continue
        if fence is not None:
            continue
        if line.startswith(("    ", "\t")) and not line.strip().startswith(("-", "*", "+")):
            continue  # indented code block (approximation)
        yield lineno, line


def headings(text: str) -> list[str]:
    out: list[str] = []
    previous = ""
    for _, line in _code_free_lines(text):
        atx = _ATX_RE.match(line)
        if atx:
            out.append(_strip_inline(atx.group(1)))
        elif _SETEXT_RE.match(line) and previous.strip() and not previous.lstrip().startswith(("-", "*", "|")):
            out.append(_strip_inline(previous.strip()))
        previous = line
    return out


def _strip_inline(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"[*`]", "", text).strip()


def slugify(heading: str) -> str:
    """GitHub's anchor algorithm: lowercase, drop punctuation except '-' and '_', spaces to '-'."""

    text = heading.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def anchors(text: str) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for heading in headings(text):
        slug = slugify(heading)
        count = seen.get(slug, 0)
        out.add(slug if count == 0 else f"{slug}-{count}")
        seen[slug] = count + 1
    for match in re.finditer(r"<a\s+(?:name|id)=[\"']([^\"']+)[\"']", text, re.IGNORECASE):
        out.add(match.group(1))
    for match in re.finditer(r"\sid=[\"']([^\"']+)[\"']", text):
        out.add(match.group(1))
    return out


def links(text: str) -> list[Link]:
    out: list[Link] = []
    for lineno, raw in _code_free_lines(text):
        line = _INLINE_CODE_RE.sub("", raw)
        ref = _REF_DEF_RE.match(line)
        if ref:
            out.append(Link(ref.group(1), lineno))
            continue
        for match in _INLINE_LINK_RE.finditer(line):
            out.append(Link(match.group(1), lineno))
        for match in _HTML_LINK_RE.finditer(line):
            out.append(Link(match.group(1), lineno))
    return out
