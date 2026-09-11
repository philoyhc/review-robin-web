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
    # The boundary matters: ``data-new-model-band2-pills-divider`` — the
    # ``||`` between the display and response pills — shares the prefix,
    # and without it the divider is counted as a pill that lost its class.
    band2 = re.findall(
        r'<span class="([^"]*)"[^>]*data-new-model-band2-pill(?![-\w])',
        instruments,
    )
    assert band2, "no Band 2 pill rendered on Instruments"
    # Every Band 2 pill carries tag-chip, which is why the rule needs no
    # `[data-new-model-band2-pill]` selector of its own.
    assert all("tag-chip" in classes for classes in band2)
