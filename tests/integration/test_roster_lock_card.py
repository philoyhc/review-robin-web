"""The four roster Setup pages' lock card, and the exit it offers.

Segment 19H Item 6. Rung 1 covers the exit; rung 2 adds the card.

The exit came first because it was already broken on two of the four
pages: ``session_relationships.html`` and ``session_observers.html``
post ``return_to`` slugs that ``_REVERT_RETURN_TO`` did not contain,
so the route fell through to Session Home. An operator reverting *so
they could edit relationships* landed somewhere else, and a 303 to a
real page looks like success — which is why nothing caught it. Rung 2
renders that control in two more states, so it had to work first.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

from ._feature_toggles import enable_observers, enable_relationships

#: The four roster Setup pages, by the ``return_to`` slug each one's
#: revert form posts. The slug is also the page's URL segment, which
#: is the whole contract: revert from page X returns to page X.
ROSTER_PAGES = ("reviewers", "reviewees", "relationships", "observers")


def _seed(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    """A session with both participant-model toggles on, so all four
    roster pages render rather than 404."""
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    enable_relationships(db, s)
    enable_observers(db, s)
    return s


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_every_roster_page_posts_a_return_to_its_own_route_honours(
    db: Session, client: TestClient, page: str
) -> None:
    """The defect rung 1 fixes, stated as its consequence: revert from
    each roster page lands back on that page, not on Session Home."""
    s = _seed(client, db, code=f"lc-rt-{page[:4]}")
    s.status = "ready"
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/revert",
        data={"confirm": "true", "return_to": page},
        follow_redirects=False,
    )

    assert response.status_code == 303, (page, response.text[:200])
    assert response.headers["location"] == (
        f"/operator/sessions/{s.id}/{page}"
    ), page


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_slug_each_template_posts_is_the_one_under_test(
    page: str
) -> None:
    """Pins the two halves together. The test above would still pass
    if a template posted something else entirely — it supplies the
    slug itself rather than reading it off the page. This asserts the
    template really posts it, so the pair cannot drift apart."""
    template = (
        f"app/web/templates/operator/session_{page}.html"
    )
    with open(template) as fh:
        markup = fh.read()

    assert f'name="return_to" value="{page}"' in markup, page


def test_an_unknown_slug_still_falls_through_to_session_home(
    db: Session, client: TestClient
) -> None:
    """Widening the allowlist must not turn it into a pass-through:
    the fallback is what stops a crafted ``return_to`` steering the
    redirect."""
    s = _seed(client, db, code="lc-rt-junk")
    s.status = "ready"
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/revert",
        data={"confirm": "true", "return_to": "../../etc"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/operator/sessions/{s.id}"
