"""A ``.btn`` never extends past its container.

Author's contract, 2026-09-19 (19Q Item 4): *"buttons should not be
going beyond their card in general"*. The mechanism is
``box-sizing: border-box`` on the base ``.btn`` rule, and the reason it
is needed at all is an asymmetry no stylesheet declares: ``<button>``
inherits ``border-box`` from the UA stylesheet and ``<a>`` does not.
This sheet has no global reset, so an ``a.btn`` given ``width: 100%``
sized as a content box and overflowed its track by its padding and
border — 34px on the Workflow card's four-slot button row, where
**Activate session** renders as an anchor on the warnings detour.

Only an *explicit* width can overflow a content box: flex and grid
compute padding and border themselves, measured identical under both box
models. So the contract has exactly two halves, and both are here — the
base rule carries ``border-box``, and nothing takes it away. Together
they cover every width-sized ``.btn`` the sheet has or gains, which is
why this file pins the property rather than a roster of rules that would
need editing every time one was added.

The layout measurement itself is not here. A Chromium-gated test would
*skip* where the tool is absent, and per ``CLAUDE.md`` a skip that
reports success is worse than a hard failure; the pixel numbers live in
the rung's PR body instead.
"""

from __future__ import annotations

import re

from ._base_css import css, rules

# A selector whose subject — the rightmost compound — is a ``.btn``.
# Anchored on the end so ``.next-action-buttons-row > .btn`` counts and
# ``.btn-row > *`` does not: the latter's subject is ``*``, and its
# items are sized by ``flex``, which respects the box model either way.
_BTN_SUBJECT = re.compile(r"(?:^|[\s>+~])(?:[a-z]+)?\.btn(?:[.:][A-Za-z0-9_-]+)*$")

_WIDTH_DECLARATION = re.compile(
    r"(?<![-\w])((?:min-|max-)?width)\s*:\s*([^;]+)"
)

# Values that name a width without constraining one.
_SIZES_NOTHING = frozenset({"auto", "0", "0px", "100%"})


def _sizes_the_box(body: str) -> bool:
    """Does this rule body actually constrain a box's width?

    Two traps, both paid for. ``min-width: 0`` *reads* as a width and
    sizes nothing, so matching a bare "width" pattern kept mutant M4
    alive — dropping the Workflow row's ``width: 100%`` left its
    ``min-width: 0`` behind and the premise check still passed. And the
    obvious repair, a negative lookahead for the zero, failed too:
    with optional whitespace either side of the colon, that whitespace
    backtracks to empty, the lookahead then inspects the space rather
    than the ``0``, and the guard it was meant to be evaporates. So the
    value is extracted and compared in Python, where what is being
    asserted is legible.

    ``100%`` counts as sizing nothing *for a ``min-`` or ``max-``
    prefix* only; a plain ``width: 100%`` is exactly the declaration
    that produced this item's defect.
    """
    for prop, value in _WIDTH_DECLARATION.findall(body):
        value = value.strip().rstrip(";").strip()
        if prop == "width" and value not in {"auto", "0", "0px"}:
            return True
        if prop != "width" and value not in _SIZES_NOTHING:
            return True
    return False


def _btn_subject_rules() -> list[tuple[str, str]]:
    """Every rule whose selector list has a ``.btn`` as some subject."""
    out = []
    for selector, body in rules(css()):
        if any(_BTN_SUBJECT.search(one.strip()) for one in selector.split(",")):
            out.append((selector, body))
    return out


def test_the_base_btn_rule_is_border_box() -> None:
    """And on the rule that reaches ``a.btn``, not a ``button``-only one.

    Asserted against ``a.btn`` specifically because the anchor is the
    whole reason the declaration exists. A tidy-up that split the
    selector list and left ``box-sizing`` on the ``button.btn`` side
    would restore the original bug while leaving a sheet that still
    greps clean for ``box-sizing``.
    """
    reached = [
        (selector, body)
        for selector, body in _btn_subject_rules()
        if any(one.strip().endswith("a.btn") for one in selector.split(","))
        and "box-sizing" in body
    ]
    assert reached, (
        "no rule whose selector list includes `a.btn` declares box-sizing. "
        "An `a.btn` given an explicit width will overflow its container by "
        "its padding and border. See spec/ui_elements.md §6."
    )
    for selector, body in reached:
        assert re.search(r"box-sizing\s*:\s*border-box", body), (
            f"`{selector}` sets box-sizing to something other than "
            f"border-box: {' '.join(body.split())}"
        )


def test_no_rule_returns_a_btn_to_content_box() -> None:
    """The other half. The base rule is worthless if a later rule,
    or a responsive override inside an ``@media``, undoes it."""
    for selector, body in _btn_subject_rules():
        assert "content-box" not in body, (
            f"`{selector}` returns a .btn to content-box, which reopens "
            f"19Q Item 4's overflow: {' '.join(body.split())}"
        )


def test_the_workflow_cards_width_sized_row_is_still_there() -> None:
    """Anti-vacuity, and the reason the two cases above are not theory.

    Both pass trivially on a sheet that gives no ``.btn`` an explicit
    width — and it was such a rule that produced the defect. If the
    Workflow card's ``width: 100%`` is ever dropped, this file's premise
    has changed and the cases above want re-reading rather than
    inheriting.
    """
    width_sized = [
        selector
        for selector, body in _btn_subject_rules()
        if _sizes_the_box(body)
    ]
    assert any("next-action-buttons-row" in one for one in width_sized), (
        "the Workflow card's button row no longer sizes its .btn children; "
        f"width-sized .btn rules found: {width_sized}"
    )
