"""ApplyDesk's screen elements styled as Review Robin's (author,
2026-11-13: "need to maintain a consistent set of screen element
styling"). Review Robin's `app/web/templates/base.html`, which its theme
customizer (`tools/theme_customizer.html`) lifts into a gallery, is the
reference: a card's edge, a pill, the Secondary button and a disabled
button resolve the same in both stylesheets, light and dark. ApplyDesk's
accent stays its own (the favicon's rose), as does its Primary.

A failure here means one stylesheet moved without the other: change both,
or record why they now differ and drop the pair."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RRW = ROOT / "app" / "web" / "templates" / "base.html"
AD = ROOT / "applydesk" / "templates" / "applydesk" / "base.html"

#: Review Robin's token, ApplyDesk's token: the same value in each theme.
TOKENS: tuple[tuple[str, str], ...] = (
    ("border-default", "border-default"),
    ("status-info-bg", "chip-info-bg"),
    ("status-info-fg", "chip-info-fg"),
    ("status-warning-bg", "chip-warn-bg"),
    ("status-warning-fg", "chip-warn-fg"),
    ("status-success-bg", "chip-ok-bg"),
    ("status-success-fg", "chip-ok-fg"),
    ("btn-secondary-bg", "btn-secondary-bg"),
    ("btn-secondary-fg", "btn-secondary-fg"),
    ("btn-secondary-border", "btn-secondary-border"),
    ("btn-secondary-bg-hover", "btn-secondary-bg-hover"),
)

#: Review Robin's rule, ApplyDesk's rule, and the properties that resolve
#: the same in both.
RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("body.ui-v2 .card", ".card", ("border",)),
    ("body.ui-v2 .card", ".fc", ("border",)),  # a builder's cards: stages, questions
    (
        "body.ui-v2 .pill",
        ".chip",
        ("padding", "border-radius", "font-size", "font-weight", "text-transform"),
    ),
    ("body.ui-v2 .btn.secondary", ".btn-secondary", ("background", "color", "border-color")),
    ('body.ui-v2 .btn[aria-disabled="true"]', ".btn[disabled]", ("opacity", "cursor")),
)


def _style(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # Jinja's own braces would read as blocks: drop its tags first.
    text = re.sub(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}", "", text, flags=re.S)
    return "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S))


def _blocks(css: str, selector: str) -> dict[str, str]:
    """Every declaration of the blocks whose selector list ends with
    ``selector``, later ones winning."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out: dict[str, str] = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors = [s.strip() for s in m.group(1).split(",")]
        if selector not in selectors:
            continue
        for decl in m.group(2).split(";"):
            if ":" in decl:
                name, value = decl.split(":", 1)
                out[name.strip()] = " ".join(value.split())
    return out


def _tokens(css: str, dark: bool) -> dict[str, str]:
    found = {k[2:]: v for k, v in _blocks(css, ":root").items() if k.startswith("--")}
    if dark:
        found |= {
            k[2:]: v
            for k, v in _blocks(css, ':root[data-theme="dark"]').items()
            if k.startswith("--")
        }
    return found


def _resolve(value: str, tokens: dict[str, str], depth: int = 0) -> str:
    assert depth < 10, value
    out = re.sub(r"var\(--([\w-]+)\)", lambda m: tokens[m.group(1)], value)
    return out if out == value else _resolve(out, tokens, depth + 1)


@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_shared_tokens_hold_the_same_values(dark: bool) -> None:
    rrw, ad = _tokens(_style(RRW), dark), _tokens(_style(AD), dark)
    for theirs, ours in TOKENS:
        assert (
            _resolve(f"var(--{ours})", ad).lower() == _resolve(f"var(--{theirs})", rrw).lower()
        ), (
            theirs,
            ours,
        )


@pytest.mark.parametrize(("theirs", "ours", "props"), RULES, ids=[r[1] for r in RULES])
@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_shared_elements_resolve_alike(
    theirs: str, ours: str, props: tuple[str, ...], dark: bool
) -> None:
    rrw_css, ad_css = _style(RRW), _style(AD)
    rrw_rule, ad_rule = _blocks(rrw_css, theirs), _blocks(ad_css, ours)
    rrw_tokens, ad_tokens = _tokens(rrw_css, dark), _tokens(ad_css, dark)
    for prop in props:
        assert prop in rrw_rule and prop in ad_rule, (theirs, ours, prop)
        want = _resolve(rrw_rule[prop], rrw_tokens)
        got = _resolve(ad_rule[prop], ad_tokens)
        assert got.lower() == want.lower(), (ours, prop, got, want)
