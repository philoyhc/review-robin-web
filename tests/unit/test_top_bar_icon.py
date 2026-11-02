"""The top bar's icon is the tab's favicon (`docs/header_chrome.md` §2):
one SVG serves both, so the two copies must not drift apart."""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "web" / "templates"


def _src(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    assert match, pattern
    return match.group(1)


def test_the_bar_icon_is_the_favicon() -> None:
    favicon = _src(
        r'<link rel="icon"[^>]*href="([^"]+)"',
        (_TEMPLATES / "base.html").read_text(encoding="utf-8"),
    )
    icon = _src(
        r'<img class="tb-icon"[^>]*src="([^"]+)"',
        (_TEMPLATES / "_partials" / "top_bar_icon.html").read_text(encoding="utf-8"),
    )
    assert icon == favicon
