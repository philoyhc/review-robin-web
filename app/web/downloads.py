"""The ``Content-Disposition`` header every download route sends.

A session code is free text, so the filename built from it can hold
characters a header cannot: Starlette encodes header values as
Latin-1, so anything past it answered 500, and a ``"`` ended the quoted
``filename`` early (findings R2, 2026-10-16). The header carries an
ASCII ``filename`` every client reads plus, when that had to change
the name, the RFC 6266 ``filename*`` that modern browsers prefer.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import quote


def _ascii_fallback(filename: str) -> str:
    out = []
    for ch in unicodedata.normalize("NFKD", filename):
        if unicodedata.combining(ch):
            continue
        out.append(ch if " " <= ch <= "~" and ch not in '"\\' else "_")
    return "".join(out)


def content_disposition(filename: str) -> str:
    """``attachment`` with ``filename``, safe to send for any name."""
    fallback = _ascii_fallback(filename)
    header = f'attachment; filename="{fallback}"'
    if fallback != filename:
        header += f"; filename*=UTF-8''{quote(filename, safe='')}"
    return header
