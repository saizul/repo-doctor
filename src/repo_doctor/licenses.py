"""Detect the SPDX identifier of a license file from characteristic phrases.

This is a fingerprint matcher, not a legal analysis: it looks for phrases that
only appear in one license family and is good enough to tell MIT from Apache-2.0
or GPL-3.0 from AGPL-3.0.
"""

from __future__ import annotations

import re

# Order matters: more specific licenses first (AGPL before GPL, LGPL before GPL).
FINGERPRINTS: list[tuple[str, tuple[str, ...]]] = [
    ("AGPL-3.0", ("gnu affero general public license", "version 3")),
    ("LGPL-3.0", ("gnu lesser general public license", "version 3")),
    ("LGPL-2.1", ("gnu lesser general public license", "version 2.1")),
    ("GPL-3.0", ("gnu general public license", "version 3")),
    ("GPL-2.0", ("gnu general public license", "version 2")),
    ("MPL-2.0", ("mozilla public license", "2.0")),
    ("Apache-2.0", ("apache license", "version 2.0")),
    ("BSL-1.0", ("boost software license",)),
    ("Unlicense", ("this is free and unencumbered software released into the public domain",)),
    ("CC0-1.0", ("cc0 1.0 universal",)),
    ("EUPL-1.2", ("european union public licence", "1.2")),
    (
        "ISC",
        (
            "permission to use, copy, modify, and/or distribute this software for any purpose",
            "provided that the above copyright notice",
        ),
    ),
    ("0BSD", ("permission to use, copy, modify, and/or distribute this software for any purpose",)),
    (
        "BSD-3-Clause",
        ("redistribution and use in source and binary forms", "neither the name of"),
    ),
    ("BSD-2-Clause", ("redistribution and use in source and binary forms",)),
    ("MIT", ("permission is hereby granted, free of charge", "the above copyright notice")),
    ("Zlib", ("this software is provided 'as-is'", "altered source versions must be plainly marked")),
]

OSI_APPROVED = {
    "AGPL-3.0", "LGPL-3.0", "LGPL-2.1", "GPL-3.0", "GPL-2.0", "MPL-2.0", "Apache-2.0", "BSL-1.0",
    "Unlicense", "EUPL-1.2", "ISC", "BSD-3-Clause", "BSD-2-Clause", "0BSD", "MIT", "Zlib",
}  # fmt: skip

_SPDX_HEADER = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+(?:\s+(?:OR|AND|WITH)\s+[A-Za-z0-9.+-]+)*)")


def _normalise(text: str) -> str:
    text = text.lower().replace("’", "'").replace("`", "'")
    return re.sub(r"\s+", " ", text)


def detect_spdx(text: str) -> str | None:
    """Return an SPDX identifier for ``text`` or ``None`` when no fingerprint matches."""

    header = _SPDX_HEADER.search(text)
    if header:
        return header.group(1).strip()
    norm = _normalise(text)
    if not norm.strip():
        return None
    for spdx, phrases in FINGERPRINTS:
        if all(p in norm for p in phrases):
            return spdx
    return None


def copyright_line(text: str) -> str | None:
    for line in text.splitlines():
        if re.match(r"\s*copyright\s+(\(c\)|©|\d{4})", line, re.IGNORECASE):
            return line.strip()
    return None
