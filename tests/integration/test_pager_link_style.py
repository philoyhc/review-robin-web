"""The row pager reads as links, not as tinted blocks.

Segment 19J Item 7 rung 4. The 19J.5 pager is not a pill, but
``.table-pager-link`` wore the pill's habits — ``padding``, a radius and
``text-decoration: none`` — so a range rendered as a block; and
``.table-pager-link.is-current`` was a solid ``--selected-bg`` fill,
putting the reserved accent shade on the one cell in the strip that does
**not** navigate.

So the pager loses a treatment rather than gaining one: ranges are
anchors and take the page's own ``a { color: var(--text-link) }`` plus
the user agent's underline, and the current cell is marked by weight.

These assertions read the **rendered strip** — the markup between
``<nav class="table-pager"`` and its ``</nav>`` — and the declaration
blocks in ``base.html``'s inline CSS, never a bare class name in the
page body: every one of these class names appears in that inline CSS on
every response, so a substring check over the whole body is vacuous
(19J.5 hit that three times).
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


def _import_reviewers(client: TestClient, session_id: int, count: int) -> None:
    rows = b"".join(
        f"Reviewer {i:04d},r{i:04d}@example.edu\n".encode() for i in range(count)
    )
    response = client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": ("r.csv", b"ReviewerName,ReviewerEmail\n" + rows, "text/csv")
        },
        follow_redirects=False,
    )
    assert response.status_code in (200, 303), response.status_code


def _strip(client: TestClient, db: Session, *, code: str) -> str:
    """The rendered pager strip, markup only."""
    review_session = _make_session(client, db, code=code)
    _import_reviewers(client, review_session.id, 556)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    start = body.index('<nav class="table-pager')
    return body[start : body.index("</nav>", start)]


def _rule(css: str, selector: str) -> str | None:
    """The declaration block for an exact selector, or None if absent."""
    match = re.search(
        re.escape(selector) + r"\s*\{([^}]*)\}", css
    )
    return match.group(1) if match else None


def _stylesheet(client: TestClient, db: Session) -> str:
    review_session = _make_session(client, db, code="pager-css")
    return client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text


def test_range_links_are_anchors_with_no_style_of_their_own(
    client: TestClient, db: Session
) -> None:
    """Every cell but the current one navigates, as a plain link."""
    strip = _strip(client, db, code="pager-style-1")

    anchors = re.findall(r'<a class="table-pager-link" href="([^"]+)"', strip)
    assert len(anchors) >= 2
    assert all("offset=" in href for href in anchors)

    # Structural, so it stays true rather than merely being true today:
    # every cell in the strip is either an anchor that navigates or the
    # one current-page span. The inert ``aria-disabled`` third kind the
    # scaffold rung left behind has no room in that count.
    cells = re.findall(r'<(\w+) class="table-pager-link[^"]*"', strip)
    assert cells.count("a") == len(anchors)
    assert cells.count("span") == 1
    assert len(cells) == len(anchors) + 1


def test_the_current_cell_is_marked_by_weight_not_by_the_reserved_shade(
    client: TestClient, db: Session
) -> None:
    """It is a ``<span>``: the one cell in the strip that cannot be
    clicked, so it must not wear the shade that means "you can"."""
    strip = _strip(client, db, code="pager-style-2")

    assert strip.count('class="table-pager-link is-current"') == 1
    assert 'aria-current="page"' in strip

    css = _stylesheet(client, db)
    block = _rule(css, ".table-pager-link.is-current")
    assert block is not None, "the current cell lost its only marking"
    assert "font-weight: 600" in block
    assert "background" not in block
    assert "--selected-bg" not in block


def test_the_pager_link_rule_carries_no_block_styling(
    client: TestClient, db: Session
) -> None:
    """``padding`` / ``border-radius`` / ``text-decoration: none`` are
    what made a range read as a chip. The bare ``.table-pager-link``
    rule is expected to be gone entirely; if some later change brings it
    back, it must not bring those three with it."""
    css = _stylesheet(client, db)
    block = _rule(css, ".table-pager-link")

    if block is not None:
        assert "padding" not in block
        assert "border-radius" not in block
        assert "text-decoration: none" not in block


def test_no_pager_rule_reaches_the_reserved_shade(
    client: TestClient, db: Session
) -> None:
    """The rung's contract, stated once and checkable by grep.

    Reads every declaration block whose selector mentions the pager and
    asserts none of them resolves to the reserved pair — directly, or
    through ``--selected-bg``.
    """
    css = _stylesheet(client, db)
    blocks = re.findall(r"(\.table-pager[^{}]*)\{([^}]*)\}", css)
    assert blocks, "no pager rules found — the selector probe is broken"

    for selector, block in blocks:
        assert "--selected-bg" not in block, (
            f"{selector.strip()} reaches the reserved shade via "
            "--selected-bg; the pager is not a control surface"
        )
        for hex_value in RESERVED_SHADE:
            assert hex_value not in block.lower(), (
                f"{selector.strip()} hard-codes {hex_value}"
            )
