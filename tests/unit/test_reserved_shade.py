"""One shade, reserved for one job.

Segment 19J Item 7. ``--blue-strong`` (``#2563eb``, light) and
``--blue-glow`` (``#4b8bf5``, dark) — the pair ``--selected-bg`` resolves
to — mean "you can act on this" on a pill or chip surface. Nothing static
carries them.

The check resolves **tokens**, not class names, for two reasons. A class
name is defined in ``base.html``'s inline CSS, which ships on every
response, so ``"tag-chip" in body`` is true of every page in the app
(19J.5 hit that three times). And the collision this item started from
was invisible at the class level: ``--lifecycle-validated-fg`` read as a
lifecycle token and resolved, four ``var()`` hops later, to exactly
``--selected-bg``'s value.

The CSS in ``base.html`` is static — no Jinja inside ``<style>`` — so
this reads the template from disk rather than rendering a page.
"""

from __future__ import annotations

import re
from pathlib import Path

BASE_HTML = Path(__file__).resolve().parents[2] / "app/web/templates/base.html"

#: Light is the bare ``:root``; dark is ``:root[data-theme="dark"]``.
#: There is no ``prefers-color-scheme`` block (see ``base.html`` line ~271).
RESERVED = {"light": "#2563eb", "dark": "#4b8bf5"}

#: Selectors permitted to reach the reserved pair. Every entry is a
#: control, and each is here because someone decided it is:
#:
#: - ``.tag-chip.is-selected`` — the filter and column chips. The
#:   selected fill *is* the affordance saying the filter is on.
#: - ``.severity-chip.active`` — the Validate page's severity filter,
#:   an ``<a>``. Already an outlined pill; active takes the shade on its
#:   border and text.
#:
#: A new entry means a new control surface, and belongs here only once
#: someone has confirmed it is one. A static pill appearing in this set
#: is the bug the file exists to catch.
CONTROL_SELECTORS = {
    "body.ui-v2 .tag-chip.is-selected",
    "body.ui-v2 .severity-chip.active",
}


def _css() -> str:
    """``base.html``'s inline stylesheet, comments stripped.

    Anchored on the ``:root {`` token block rather than on ``<style>``:
    the string ``<style>`` appears first inside a *comment* in the
    theme-bootstrap script above it, and slicing from there drags that
    script's JavaScript braces in as if they were CSS rules.
    """
    src = BASE_HTML.read_text(encoding="utf-8")
    style = src[src.index(":root {") : src.index("</style>")]
    return re.sub(r"/\*.*?\*/", " ", style, flags=re.S)


def _rules(css: str) -> list[tuple[str, str]]:
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


def _block(css: str, marker: str) -> str:
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


def _token_maps(css: str) -> dict[str, dict[str, str]]:
    """``{theme: {token: literal}}``, each ``var()`` chain followed out."""
    declarations = re.compile(r"(--[a-z0-9-]+)\s*:\s*([^;]+);")
    raw: dict[str, dict[str, str]] = {}
    for theme, marker in (
        ("light", ":root {"),
        ("dark", ':root[data-theme="dark"] {'),
    ):
        raw[theme] = dict(declarations.findall(_block(css, marker)))
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


def test_the_token_maps_resolve_at_all() -> None:
    """Guards the guards: a parser that silently returns nothing would
    make every assertion below pass for the wrong reason."""
    tokens = _token_maps(_css())

    assert tokens["light"]["--selected-bg"] == RESERVED["light"]
    assert tokens["dark"]["--selected-bg"] == RESERVED["dark"]
    assert len(tokens["light"]) > 100


def test_validated_is_not_painted_in_the_control_shade() -> None:
    """The one static class that was. It takes the foreground pair
    ``pill-info`` already uses, so the fix adds no token and the
    lifecycle ramp still reads amber → cool → green."""
    tokens = _token_maps(_css())

    assert tokens["light"]["--lifecycle-validated-fg"] == "#1e40af"  # blue-deeper
    assert tokens["dark"]["--lifecycle-validated-fg"] == "#93c5fd"  # blue-soft

    for theme in RESERVED:
        assert tokens[theme]["--lifecycle-validated-fg"] != RESERVED[theme]


def test_only_controls_reach_the_reserved_shade() -> None:
    """The rule itself, over every pill and chip rule in the sheet."""
    css = _css()
    tokens = _token_maps(css)

    found: set[str] = set()
    scanned = 0
    for selector, body in _rules(css):
        if not re.search(r"\.(?:[a-z0-9-]*(?:pill|chip))\b", selector):
            continue
        scanned += 1
        for theme, reserved in RESERVED.items():
            for token in re.findall(r"var\((--[a-z0-9-]+)\)", body):
                if tokens[theme].get(token) == reserved:
                    found.add(selector)

    # The sheet carried 36 pill/chip rules when this was written. The
    # floor is here because a parser that quietly matches nothing makes
    # the real assertion below pass for the worst possible reason.
    assert scanned >= 30, f"only {scanned} pill/chip rules scanned"

    assert found == CONTROL_SELECTORS, (
        "pill/chip rules reaching the reserved shade changed.\n"
        f"  unexpected: {sorted(found - CONTROL_SELECTORS)}\n"
        f"  missing:    {sorted(CONTROL_SELECTORS - found)}\n"
        "A new entry is only allowed once it is confirmed to be a "
        "control; a static pill here is the collision Item 7 removes."
    )
