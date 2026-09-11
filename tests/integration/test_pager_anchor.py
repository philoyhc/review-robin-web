"""A page turn lands on the table, not on the page header.

Segment 19J Item 8. The pager's ranges are plain anchors, so clicking
one is an ordinary navigation and the browser lands at the top of the
document — and on the pages the pager exists for, the table is well
below the fold under the filter card and the chip row. Every page turn
cost a scroll.

Each range link now carries a ``#<noun>-table`` fragment. It is still a
full reload; the fragment only decides where the browser stops.

The assertion that matters is the **pair**: every range href ends in the
page's anchor, *and* that anchor names an id the same response actually
contains. A fragment pointing at nothing fails exactly like no fragment
at all — the browser stays at the top — and the two are indistinguishable
in a diff, so checking only the href would leave the real failure mode
uncovered.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

#: The seven routes that supply an anchor, and the template each one
#: renders. Checked at source level rather than by seeding seven rosters:
#: Relationships and Observers need a populated session to render at all,
#: and the failure this guards — an anchor naming an id the page does not
#: have — is a mismatch between two files, not a runtime behaviour.
ROUTE_TEMPLATES = {
    "_setup_reviewers.py": "session_reviewers.html",
    "_setup_reviewees.py": "session_reviewees.html",
    "_setup_relationships.py": "session_relationships.html",
    "_setup_observers.py": "session_observers.html",
    "_assignments.py": "session_assignments.html",
    "_operations.py": None,  # two anchors; resolved per value below
}

ANCHOR_TEMPLATES = {
    "reviewers-pager": "session_reviewers.html",
    "reviewees-pager": "session_reviewees.html",
    "relationships-pager": "session_relationships.html",
    "observers-pager": "session_observers.html",
    "assignments-pager": "session_assignments.html",
    "invitations-pager": "session_invitations.html",
    "responses-pager": "session_responses.html",
}


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


def _ranges(body: str) -> list[str]:
    """Every range href in the rendered strips, both of them."""
    return re.findall(r'<a class="table-pager-link"\s+href="([^"]+)"', body)


def test_every_range_link_lands_on_the_table(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="anchor-1")
    _import_reviewers(client, review_session.id, 556)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    hrefs = _ranges(body)
    # Three pages of 556, rendered above and below the table.
    assert len(hrefs) >= 4

    for href in hrefs:
        assert href.endswith("#reviewers-pager"), href
        # The fragment rides on the link; the offset is untouched.
        assert re.search(r"offset=\d+#reviewers-pager$", href), href


def test_the_anchor_names_an_id_the_page_actually_has(
    client: TestClient, db: Session
) -> None:
    """The half that catches a renamed table.

    A fragment pointing at nothing leaves the browser at the top of the
    document — the exact behaviour this item removes — and looks
    identical to a working one in the markup.
    """
    review_session = _make_session(client, db, code="anchor-2")
    _import_reviewers(client, review_session.id, 556)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    anchors = {href.split("#", 1)[1] for href in _ranges(body)}
    assert anchors, "no range links rendered"

    for anchor in anchors:
        assert f'id="{anchor}"' in body, (
            f"the pager points at #{anchor}, which this page does not "
            "contain — the browser would stay at the top"
        )


def test_every_pager_route_supplies_an_anchor_that_exists() -> None:
    """The rename guard, across all seven pages.

    The route passes the id rather than the macro deriving it — which is
    the safer choice only if something checks the two still agree. This
    is that something: every ``pager_anchor`` a route declares must name
    an ``id`` its own template carries.
    """
    routes = Path("app/web/routes_operator")
    templates = Path("app/web/templates/operator")

    declared: list[str] = []
    for route in ROUTE_TEMPLATES:
        source = (routes / route).read_text(encoding="utf-8")
        declared += re.findall(r'"pager_anchor": "([^"]+)"', source)

    assert sorted(declared) == sorted(ANCHOR_TEMPLATES), (
        f"routes declare {sorted(declared)}; expected "
        f"{sorted(ANCHOR_TEMPLATES)}"
    )

    for anchor, template in ANCHOR_TEMPLATES.items():
        markup = (templates / template).read_text(
            encoding="utf-8", errors="replace"
        )
        assert f'id="{anchor.replace("-pager", "-table")}"' in markup, (
            f"{template} has no table for its pager to sit above"
        )
        # The id and the landing margin both live in the shared
        # partial now, so the per-template assertion is that the page
        # includes it at all.
        assert "_preview_pager.html" in markup, (
            f"{template} does not render the pager partial"
        )


def test_the_anchored_strip_keeps_a_landing_margin(
    client: TestClient, db: Session
) -> None:
    """Without it the strip sits flush against the viewport's edge,
    which reads as the page starting there rather than as scrolled."""
    review_session = _make_session(client, db, code="anchor-margin")
    # Enough rows to page: the anchored element is the strip, and the
    # strip only renders when there is more than one page to offer.
    _import_reviewers(client, review_session.id, 556)
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    rule = re.search(r"\.table-pager-anchored\s*\{([^}]*)\}", body)
    assert rule is not None, "the landing-margin rule is gone"
    assert "scroll-margin-top" in rule.group(1)

    # And it is on the element the fragment points at, not merely
    # declared somewhere in the sheet.
    assert re.search(
        r'<nav class="table-pager table-pager-anchored"\s+id="reviewers-pager"',
        body,
    )
    # Exactly one element carries the id: the bottom copy must not, or
    # the fragment would be ambiguous and the browser would pick the
    # first — which is the top strip by luck rather than by design.
    assert body.count('id="reviewers-pager"') == 1
