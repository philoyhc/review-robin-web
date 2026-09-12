"""One shade, reserved for one job.

Segment 19J Items 7 and 10. ``--blue-strong`` (``#2563eb``, light) and
``--blue-glow`` (``#4b8bf5``, dark) — the pair ``--selected-bg`` resolves
to — mean "you can act on this". Nothing static carries them.

**The scope is the ambiguity, not the element type** (author,
2026-09-11, closing Item 10). The rule exists because a pill and a chip
have a *dual nature*: the same rounded shape states a fact in one place
and offers a click in another, and before 19J.7 the only thing telling
them apart was ``cursor: pointer`` — invisible until the pointer is on
it, absent on touch, absent from every screenshot. Where that ambiguity
is absent the rule has nothing to do: there is no such thing as a
clickable ``.banner-info`` that looks like a static one, so the accent
border it carries misleads nobody.

So the selector filter below is a **consequence** of the rule and not
the rule itself, and it grows when a new element class acquires the
same dual nature. ``.btn-icon`` acquired it at 19J.9 — the pager's
inactive steps render as ``<span class="btn-icon …">`` beside live ones
that are anchors — which is why it is scanned here. Anything else that
starts rendering in both an inert and an interactive form belongs in
this filter too.

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

# The stylesheet parser moved to ``_base_css`` at 19K.7 when a second
# caller appeared; the aliases keep this file's body as it was.
from ._base_css import css as _css
from ._base_css import rules as _rules
from ._base_css import token_maps as _token_maps

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
#:   border and text, and is the precedent rung 3 generalised.
#: - the three-selector chip rule — every ``.tag-chip`` (which is every
#:   Band 2 pill too), plus the lobby's Clear and AND/OR chips. Added at
#:   rung 3, which is what gives a chip its edge. Checked before it
#:   landed: every element carrying ``.tag-chip`` in the app is
#:   interactive, and ``is-disabled`` — the one inert variant — cancels
#:   the edge rather than inheriting it.
#:
#: - ``.btn-icon.action`` — the blue "+add" icon button. In this set
#:   since 19J.10 widened the filter past pills and chips: the class
#:   now renders inert too (the pager's inactive steps), so it carries
#:   the ambiguity the rule is about. The inert form takes
#:   ``--text-subtle`` at 0.4 opacity and never the accent, which is
#:   the vocabulary holding rather than an exception to it.
#:
#: A new entry means a new control surface, and belongs here only once
#: someone has confirmed it is one. A static pill appearing in this set
#: is the bug the file exists to catch.
CONTROL_SELECTORS = {
    "body.ui-v2 .tag-chip.is-selected",
    "body.ui-v2 .severity-chip.active",
    "body.ui-v2 .btn-icon.action",
    (
        "body.ui-v2 .tag-chip, body.ui-v2 .pill.pill-tag-clear, "
        "body.ui-v2 .pill.tag-mode-chip"
    ),
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
    """The rule itself, over every rule whose element class carries the
    static-vs-interactive ambiguity (see the module docstring)."""
    css = _css()
    tokens = _token_maps(css)

    found: set[str] = set()
    scanned = 0
    for selector, body in _rules(css):
        if not re.search(
            r"\.(?:[a-z0-9-]*(?:pill|chip)|btn-icon)\b", selector
        ):
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
