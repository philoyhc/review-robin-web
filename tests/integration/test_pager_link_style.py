"""The pager reaches the reserved shade nowhere.

Segment 19J Item 7 rung 4, carried forward. That rung stripped
``.table-pager-link`` of the pill's habits — ``padding``, a radius,
``text-decoration: none`` — and took the solid ``--selected-bg`` off
``.table-pager-link.is-current``, which had put the reserved accent
shade on the one cell in the strip that did **not** navigate.

19J.9 rung 2 then retired the strip outright, so the three tests about
its treatment went with it: there is no range strip to read as a row of
tinted blocks, and no current cell to mark, because the menu's summary
says where you are while also being the way to leave.

What survives is the rung's actual contract, and it now covers more
than it did: **no rule whose selector mentions the pager resolves to
the reserved pair** — not the cluster, not the steps, not the menu. The
new classes were named ``.table-pager-*`` precisely so this sweep would
pick them up without anyone remembering to add them.

The assertions read declaration blocks in ``base.html``'s inline CSS,
never a bare class name in the page body: every one of these names
appears in that CSS on every response, so a substring check over the
whole body is vacuous (19J.5 hit that three times).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

#: The pair reserved for things the operator can act on, resolved from
#: ``--blue-strong`` (light) and ``--blue-glow`` (dark). ``--selected-bg``
#: is how a pill or chip reaches them.
RESERVED_SHADE = ("#2563eb", "#4b8bf5")


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
    """The declaration block for an exact selector, or None if absent."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    return match.group(1) if match else None


def _stylesheet(client: TestClient, db: Session) -> str:
    review_session = _make_session(client, db, code="pager-css")
    return client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text


def test_the_retired_strip_left_no_rules_behind(
    client: TestClient, db: Session
) -> None:
    """A rule for markup nothing renders is worse than no rule: the next
    reader has to work out whether it is dead or whether they have
    missed the page that uses it."""
    css = _stylesheet(client, db)

    for selector in (
        ".table-pager-link",
        ".table-pager-link.is-current",
        ".table-pager-gap",
        ".table-pager-bottom",
    ):
        assert _rule(css, selector) is None, f"{selector} outlived the strip"


def test_no_pager_rule_reaches_the_reserved_shade(
    client: TestClient, db: Session
) -> None:
    """The rung's contract, stated once and checkable by grep.

    Reads every declaration block whose selector mentions the pager and
    asserts none of them resolves to the reserved pair — directly, or
    through ``--selected-bg``. Since 19J.9 that sweep covers the cluster,
    its four steps and its range menu, because every one of those class
    names starts with ``.table-pager``.
    """
    css = _stylesheet(client, db)
    blocks = re.findall(r"(\.table-pager[^{}]*)\{([^}]*)\}", css)
    assert blocks, "no pager rules found — the selector probe is broken"
    # The cluster alone is more rules than the strip ever had; a probe
    # that silently matched two of them would pass while covering
    # nothing.
    assert len(blocks) >= 8, f"only {len(blocks)} pager rules scanned"

    for selector, block in blocks:
        assert "--selected-bg" not in block, (
            f"{selector.strip()} reaches the reserved shade via "
            "--selected-bg; the pager is not a selection surface"
        )
        for hex_value in RESERVED_SHADE:
            assert hex_value not in block.lower(), (
                f"{selector.strip()} hard-codes {hex_value}"
            )


def test_the_glyph_buttons_and_menu_rows_carry_no_link_underline(
    client: TestClient, db: Session
) -> None:
    """The one place 19J.9 deliberately contradicts 19J.7 rung 4.

    That rung took ``text-decoration: none`` **off** ``.table-pager-link``
    so a range would read as the link it was — correct, for inline prose
    in a strip. The cluster's cells are not that: the four steps are the
    ``.btn-icon`` role, the same borderless glyph button as the
    move-up / move-down arrows, and an underlined ``»`` reads as a typo;
    the menu's entries are rows in a panel, where underlining every one
    makes a list harder to scan rather than easier.

    Both are anchors, so the page's own ``a`` rule underlines them
    unless something says otherwise. This is the something, and it is
    pinned because the reason is not visible from the rule.
    """
    css = _stylesheet(client, db)

    for selector in (".table-pager-step", ".table-pager-menu-item"):
        block = _rule(css, f"body.ui-v2 {selector}")
        assert block is not None, f"{selector} lost its rule"
        assert "text-decoration: none" in block, (
            f"{selector} would take the page's link underline"
        )

    # And each has a hover state, so an anchor that looks like neither a
    # link nor a button still says it is live.
    assert _rule(css, "body.ui-v2 a.table-pager-step:hover") is not None
    assert _rule(css, "body.ui-v2 a.table-pager-menu-item:hover") is not None
