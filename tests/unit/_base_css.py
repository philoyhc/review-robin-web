"""Parsing helpers for ``base.html``'s inline stylesheet.

Extracted at 19K.7 from ``test_reserved_shade.py``, which wrote them
first and is now one of two callers. The extraction is the point: each
function below encodes a trap that cost someone a debugging session,
and a second copy of this parser would not have inherited the fixes.
The functions are unchanged from that file — only the leading
underscores are gone, these being a module boundary now rather than a
file-private detail.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE_HTML = Path(__file__).resolve().parents[2] / "app/web/templates/base.html"


def css() -> str:
    """``base.html``'s inline stylesheet, comments stripped.

    Anchored on the ``:root {`` token block rather than on ``<style>``:
    the string ``<style>`` appears first inside a *comment* in the
    theme-bootstrap script above it, and slicing from there drags that
    script's JavaScript braces in as if they were CSS rules.
    """
    src = BASE_HTML.read_text(encoding="utf-8")
    style = src[src.index(":root {") : src.index("</style>")]
    return re.sub(r"/\*.*?\*/", " ", style, flags=re.S)


def rules(css: str) -> list[tuple[str, str]]:
    """Every innermost ``selector { declarations }`` pair.

    Matching only blocks whose body holds no brace skips the ``@media``
    wrappers and lands on the rules inside them, which is what we want:
    a responsive override is as capable of painting the shade as any
    other rule.

    The selector needs no anchor: ``[^{}]*`` cannot cross a brace, so it
    starts after the previous rule's ``}`` on its own. An earlier draft
    of this file wrote ``(?:^|[{}])`` to say so explicitly and **halved
    the result** — the engine consumed the closing brace each time, so
    the next rule had no delimiter left to match and every second rule
    was skipped. It found 269 of 519 rules, and none of the control
    selectors; only the non-empty expected set below turned that into a
    failure instead of a pass.
    """
    return [
        (" ".join(m.group(1).split()), m.group(2))
        for m in re.finditer(r"([^{}]*)\{([^{}]*)\}", css)
    ]


def block(css: str, marker: str) -> str:
    """The braced body opened by ``marker``, by counting braces.

    The two token blocks are found this way rather than through
    ``_rules`` because a single stray brace anywhere earlier in the
    sheet — inside a ``content:`` string, say — would slip that regex
    out of alignment and silently drop a block, which is exactly the
    failure a guard file must not have.
    """
    start = css.index(marker) + len(marker)
    depth = 1
    for offset, character in enumerate(css[start:]):
        depth += {"{": 1, "}": -1}.get(character, 0)
        if depth == 0:
            return css[start : start + offset]
    raise AssertionError(f"unclosed block for {marker!r}")


def token_maps(css: str) -> dict[str, dict[str, str]]:
    """``{theme: {token: literal}}``, each ``var()`` chain followed out."""
    declarations = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
    raw: dict[str, dict[str, str]] = {}
    for theme, marker in (
        ("light", ":root {"),
        ("dark", ':root[data-theme="dark"] {'),
    ):
        raw[theme] = dict(declarations.findall(block(css, marker)))
    # Dark redefines only what it changes, so it inherits light's rest.
    raw["dark"] = {**raw["light"], **raw["dark"]}

    def resolve(token: str, source: dict[str, str], depth: int = 0) -> str | None:
        value = source.get(token)
        if value is None or depth > 8:
            return value
        chained = re.match(r"var\((--[a-z0-9-]+)\)", value.strip())
        return resolve(chained.group(1), source, depth + 1) if chained else value.strip()

    return {
        theme: {
            token: resolved
            for token in source
            if (resolved := resolve(token, source)) is not None
        }
        for theme, source in raw.items()
    }
