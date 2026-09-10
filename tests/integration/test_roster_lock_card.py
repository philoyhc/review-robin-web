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


LOCKED = ("ready", "expired", "archived")
EDITABLE = ("draft", "validated")
ALL_STATES = EDITABLE + LOCKED

_CARD_OPEN = '<div class="card lock">'


def _page(client: TestClient, s: ReviewSession, page: str) -> str:
    response = client.get(f"/operator/sessions/{s.id}/{page}")
    assert response.status_code == 200, (page, response.status_code)
    return response.text


def _lock_card(client: TestClient, s: ReviewSession, page: str) -> str:
    """The lock card's own markup, sliced at its closing tag.

    Every assertion about the card is made against this rather than
    against the page, because 19I spent seven findings on substrings
    that matched somewhere else entirely — a page's own CSS, a comment
    written to explain the thing being checked, a search datalist. A
    depth-counting slice costs ten lines and makes "not in" mean what
    it says.
    """
    body = _page(client, s, page)
    start = body.index(_CARD_OPEN)
    depth, i = 0, start
    while True:
        nxt_open = body.find("<div", i)
        nxt_close = body.index("</div>", i)
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
            continue
        depth -= 1
        i = nxt_close + len("</div>")
        if depth == 0:
            return body[start:i]


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
def test_the_slug_each_page_renders_is_the_one_under_test(
    db: Session, client: TestClient, page: str
) -> None:
    """Pins the two halves together. The redirect test above supplies
    the slug itself, so it would pass even if a page rendered someone
    else's. This reads the slug off the rendered card.

    Asserted against the response rather than the template source: the
    card moved into a shared partial at rung 2, and a test that greps
    a template file re-breaks every time the markup moves."""
    s = _seed(client, db, code=f"lc-slug-{page[:4]}")
    s.status = "ready"
    db.commit()

    card = _lock_card(client, s, page)

    assert f'name="return_to" value="{page}"' in card, page


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


# ------------------------------------------------------------------ #
# Rung 2 — the card covers every state the page locks.
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("state", ALL_STATES)
@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_card_renders_exactly_where_the_page_is_locked(
    db: Session, client: TestClient, page: str, state: str
) -> None:
    """The gap this item closes. The card was keyed to ``is_ready``
    while every control on the page moved to ``is_editable`` at 19I.3,
    so ``expired`` and ``archived`` were correct and silent."""
    s = _seed(client, db, code=f"lc-r-{page[:4]}-{state[:4]}")
    s.status = state
    db.commit()

    present = _CARD_OPEN in _page(client, s, page)

    assert present is (state in LOCKED), (page, state)


@pytest.mark.parametrize(
    ("state", "phrase"),
    (
        ("ready", "cannot be modified while the session is ongoing"),
        ("expired", "cannot be modified because the session is closed"),
        ("archived", "cannot be modified because the session is archived"),
    ),
)
@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_card_names_the_state_it_is_explaining(
    db: Session, client: TestClient, page: str, state: str, phrase: str
) -> None:
    """``expired`` reads **Closed** to an operator
    (``app/services/lifecycle_display.py``), so the copy says closed,
    not expired — the rule Instruments already follows."""
    s = _seed(client, db, code=f"lc-c-{page[:4]}-{state[:4]}")
    s.status = state
    db.commit()

    assert phrase in _lock_card(client, s, page), (page, state)


@pytest.mark.parametrize(
    ("page", "subject"),
    (
        ("reviewers", "The reviewers cannot be modified"),
        ("reviewees", "The reviewees cannot be modified"),
        ("relationships", "Relationships cannot be modified"),
        ("observers", "The observers cannot be modified"),
    ),
)
def test_each_page_names_its_own_roster(
    db: Session, client: TestClient, page: str, subject: str
) -> None:
    """The one thing a shared partial could get wrong for everyone at
    once: four pages rendering the same noun."""
    s = _seed(client, db, code=f"lc-n-{page[:4]}")
    s.status = "expired"
    db.commit()

    assert subject in _lock_card(client, s, page), page


@pytest.mark.parametrize("state", ("ready", "expired"))
@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_revertable_states_carry_the_inline_revert_form(
    db: Session, client: TestClient, page: str, state: str
) -> None:
    s = _seed(client, db, code=f"lc-f-{page[:4]}-{state[:4]}")
    s.status = state
    db.commit()

    card = _lock_card(client, s, page)

    assert f'action="/operator/sessions/{s.id}/revert"' in card, (page, state)
    assert 'data-delete-btn="revert"' in card, (page, state)


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_archived_names_unarchive_instead_of_revert(
    db: Session, client: TestClient, page: str
) -> None:
    """``/revert`` answers 409 from ``archived``, so a revert form here
    would be the dead control 19I.3 spent a PR removing. Asserted
    against the card's own markup — the page links plenty of things."""
    s = _seed(client, db, code=f"lc-a-{page[:4]}")
    s.status = "archived"
    db.commit()

    card = _lock_card(client, s, page)

    assert 'href="/operator/sessions/archived"' in card, page
    assert "Unarchive" in card, page
    assert f'action="/operator/sessions/{s.id}/revert"' not in card, page
    assert 'data-delete-btn="revert"' not in card, page


@pytest.mark.parametrize("state", ("ready", "expired"))
@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_offered_revert_actually_works(
    db: Session, client: TestClient, page: str, state: str
) -> None:
    """A control the card offers has to do something, and land where
    it says. ``revert_session_to_draft`` accepts ``ready`` and
    ``expired``; rung 1 made the four slugs resolve."""
    s = _seed(client, db, code=f"lc-w-{page[:4]}-{state[:4]}")
    s.status = state
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/revert",
        data={"confirm": "true", "return_to": page},
        follow_redirects=False,
    )
    db.expire_all()

    assert response.status_code == 303, (page, state, response.text[:200])
    assert response.headers["location"] == (
        f"/operator/sessions/{s.id}/{page}"
    ), (page, state)
    assert db.get(ReviewSession, s.id).status == "draft", (page, state)


@pytest.mark.parametrize("page", ROSTER_PAGES)
def test_the_revert_archived_offers_no_control_would_have_failed(
    db: Session, client: TestClient, page: str
) -> None:
    """Why the archived branch carries no form, stated as the route's
    own answer rather than as a claim about it."""
    s = _seed(client, db, code=f"lc-409-{page[:4]}")
    s.status = "archived"
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/revert",
        data={"confirm": "true", "return_to": page},
        follow_redirects=False,
    )

    assert response.status_code == 409, (page, response.status_code)
