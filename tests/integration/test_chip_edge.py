"""A chip looks clickable, and an inert one does not.

Segment 19J Item 7 rung 3 — the rung the whole item was opened for. Until
it landed, the only thing separating a clickable pill from a label was
``cursor: pointer`` on ``.tag-chip``: invisible until the pointer is
already over the chip, absent on touch, and absent from every screencap
in the Guide.

Every chip now carries the reserved accent shade as a 2px edge. The
**fill is untouched** — a Band 1 "not set" chip keeps its amber, because
amber is a status and the edge is an affordance, and both are true of
that chip at once.

Two halves, asserted together, because either alone is worthless: the
rendered element has to carry the class the rule targets, *and* the rule
has to declare the edge. A class name on its own proves nothing — every
one of these ships in ``base.html``'s inline CSS on every response — and
a CSS rule on its own may match no element in the app.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

#: ``--selected-bg``: ``#2563eb`` light, ``#4b8bf5`` dark. The edge is
#: declared through the token, which is what ties this rung to
#: ``tests/unit/test_reserved_shade.py``.
EDGE = "var(--selected-bg)"


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _rule(css: str, selector: str) -> str | None:
    """The declaration block for an exact selector, or None."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else None


def _chip_rule(css: str) -> str:
    """The block that gives every chip its edge."""
    block = _rule(
        css,
        "body.ui-v2 .tag-chip,\n      body.ui-v2 .pill.pill-tag-clear,"
        "\n      body.ui-v2 .pill.tag-mode-chip",
    )
    assert block is not None, "the chip-edge rule is gone or was resplit"
    return block


def test_the_chip_rule_declares_a_two_pixel_edge_in_the_reserved_shade(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="19j7r3-1")
    css = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    block = _chip_rule(css)

    assert f"border-color: {EDGE}" in block
    # Thickened by an inset shadow, never by border-width: the box has to
    # stay the size the transparent baseline border reserved for it.
    assert f"box-shadow: inset 0 0 0 1px {EDGE}" in block
    assert "border-width" not in block

    baseline = _rule(css, "body.ui-v2 .pill")
    assert baseline is not None
    assert "border: 1px solid transparent" in baseline


def test_the_chip_rule_leaves_the_fill_alone(
    client: TestClient, db: Session
) -> None:
    """The decision this rung turns on.

    A blanket ``background: transparent`` would have read as the tidier
    rule and would have erased ``pill-empty``'s amber from Band 1's "not
    set" chips — trading a status signal for an affordance when the chip
    needs both.
    """
    review_session = _make_session(client, db, code="19j7r3-2")
    css = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text

    assert "background" not in _chip_rule(css)


def test_an_inert_chip_does_not_wear_the_shade(
    client: TestClient, db: Session
) -> None:
    """``is-disabled`` sets ``cursor: default``. A chip that says it
    cannot be clicked must not also say it can."""
    review_session = _make_session(client, db, code="19j7r3-3")
    css = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text

    block = _rule(css, "body.ui-v2 .tag-chip.is-disabled")
    assert block is not None
    assert "border-color: transparent" in block
    assert "box-shadow: none" in block
    # Specificity, spelled out: (0,3,1) beats the chip rule's (0,2,1),
    # so the cancellation actually wins rather than merely being written.
    assert css.index("body.ui-v2 .tag-chip.is-disabled") > css.index(
        "body.ui-v2 .tag-chip,"
    )


def test_the_chips_the_rule_targets_are_really_on_the_page(
    client: TestClient, db: Session
) -> None:
    """The other half. A rule matching nothing would pass every
    assertion above."""
    review_session = _make_session(client, db, code="19j7r3-4")

    assignments = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
    ).text
    toggles = re.findall(
        r'<span class="([^"]*tag-chip[^"]*)"[^>]*data-col-toggle=', assignments
    )
    assert toggles, "no column-toggle chip rendered on Assignments"

    instruments = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The response pills retired in 19T Item 9 (the display pills in
    # Item 8), so the page's clickable chips are the visibility editor's
    # cycle chips; each carries tag-chip. No Band 2 pill remains.
    assert not re.search(r"data-new-model-band2-pill(?![-\w])", instruments)
    cycles = [
        (m.group(1), m.group(0))
        for m in re.finditer(r'<span class="([^"]*)"[^>]*>', instruments)
        if "data-new-model-vp-cycle-audience" in m.group(0)
    ]
    assert cycles, "no visibility cycle chip rendered on Instruments"
    for classes, tag in cycles:
        assert "tag-chip" in classes, tag


def test_a_locked_chip_drops_the_edge_and_keeps_its_state(
    client: TestClient, db: Session
) -> None:
    """19U Item 3: Session Home's optional-tab chips lock with the card.
    A locked chip cancels the edge and the pointer, as ``is-disabled``
    does, but says on or off in the card's display-value colors rather
    than the reserved shade, and is not struck through."""
    review_session = _make_session(client, db, code="19u3-locked")
    css = client.get(f"/operator/sessions/{review_session.id}").text

    block = _rule(css, "body.ui-v2 .tag-chip.is-locked")
    assert block is not None
    assert "cursor: default" in block
    assert "border-color: transparent" in block
    assert "box-shadow: none" in block
    assert "line-through" not in block
    assert css.index("body.ui-v2 .tag-chip.is-locked {") > css.index(
        "body.ui-v2 .tag-chip,"
    )
    on = _rule(
        css,
        "body.ui-v2 .tag-chip.is-locked.is-selected,\n"
        "      body.ui-v2 .tag-chip.is-locked:has(> input:checked)",
    )
    assert on is not None
    assert "var(--config-value-bg)" in on and EDGE not in on
    assert css.index("body.ui-v2 .tag-chip.is-locked.is-selected") > css.index(
        "body.ui-v2 .tag-chip.is-selected,"
    )
    off = _rule(
        css,
        "body.ui-v2 .tag-chip.is-locked:not(.is-selected):not(:has(> input:checked))",
    )
    assert off is not None and "opacity: 0.55" in off


def test_a_checkbox_chip_fills_from_its_box(
    client: TestClient, db: Session
) -> None:
    """A chip wrapping a checkbox is selected when the box is ticked, so a
    Cancel's ``form.reset()`` repaints it with no script."""
    review_session = _make_session(client, db, code="19u3-has")
    css = client.get(f"/operator/sessions/{review_session.id}").text

    block = _rule(
        css,
        "body.ui-v2 .tag-chip.is-selected,\n"
        "      body.ui-v2 .tag-chip:has(> input:checked)",
    )
    assert block is not None
    assert "var(--selected-bg)" in block
    # A chip that is a ``<label>`` must not take ``body.ui-v2 label``'s
    # block box and margins (read on #2893: nothing else pinned these).
    label = _rule(css, "body.ui-v2 label.tag-chip")
    assert label is not None
    assert "display: inline-block" in label
    assert "margin: 0 var(--space-1) 0 0" in label


def test_a_linked_role_pill_wears_the_edge_and_a_span_does_not(
    client: TestClient, db: Session
) -> None:
    """Findings E13: the ``/me`` dashboard's role pills and the role
    navigator's other-role pills are anchors when they lead somewhere, so
    they carry the chip edge. The rule names ``a.pill``, which is what
    keeps the ``<span>`` forms — the current role, an unreachable one —
    static labels: a selector broadened past the anchor stops matching
    the exact lookup below, and ``test_reserved_shade``'s allowlist.
    That the templates render the anchors is pinned by
    ``test_me_surface_role_chips.py`` and ``test_me_dashboard_links.py``."""
    review_session = _make_session(client, db, code="e13-role-edge")
    css = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text

    block = _rule(
        css,
        "body.ui-v2 a.pill.pill-role-reviewer,\n"
        "      body.ui-v2 a.pill.pill-role-reviewee,\n"
        "      body.ui-v2 a.pill.pill-role-observer",
    )
    assert block is not None, "the linked role-pill edge rule is gone"
    assert f"border-color: {EDGE}" in block
    assert f"box-shadow: inset 0 0 0 1px {EDGE}" in block
    assert "background" not in block
