"""The selection surface renders only where it can act — 19I Item 3 PR 1.

The four roster pages gated row selection on `is_ready`, which is *only*
`status == "ready"`. So an `expired` or `archived` session rendered
checkboxes and a live Delete while every mutation 409'd, and a `ready`
session rendered a Delete that nothing could ever enable.

The gate is now `lifecycle.is_editable` — `draft` or `validated` — which
is what `_require_editable` enforces on the routes, so the page and the
route agree by construction rather than by two lists kept in step.

Observers is the deliberate exception on **checkboxes only**: theirs
drive the cohort rule editor, which stays live until `archived`. Its
bulk *card* follows the same gate as everyone else's.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
)

EDITABLE = ("draft", "validated")
FROZEN = ("ready", "expired", "archived")
ALL_STATUSES = EDITABLE + FROZEN
# Observers' checkboxes are not in this list — see the module docstring.
CHECKBOX_PAGES = ("reviewers", "reviewees", "relationships")
ALL_PAGES = CHECKBOX_PAGES + ("observers",)

SELECT_CLASS = {
    "reviewers": "reviewer-select",
    "reviewees": "reviewee-select",
    "relationships": "relationship-select",
    "observers": "observer-select",
}


def _session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.relationships_enabled = True
    s.observers_enabled = True
    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.add(Observer(session_id=s.id, email="o@example.edu", display_name="O"))
    db.flush()
    db.add(
        Relationship(
            session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        )
    )
    db.commit()
    return s


def _render(client: TestClient, s: ReviewSession, page: str) -> str:
    r = client.get(f"/operator/sessions/{s.id}/{page}")
    assert r.status_code == 200, (page, s.status, r.status_code)
    return r.text


@pytest.mark.parametrize("page", CHECKBOX_PAGES)
@pytest.mark.parametrize("status", EDITABLE)
def test_the_selection_surface_renders_while_editable(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    s = _session(client, db, code=f"sl-on-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert f'class="{SELECT_CLASS[page]}"' in body, "row checkboxes"
    assert f'id="{page}-delete-btn"' in body, "Delete"
    assert f'id="{page}-edit-btn"' in body, "Edit"
    assert f'id="{page}-delete-confirm"' in body, "the delete gate"
    assert f'id="{page}-bulk-form"' in body, "the form they post to"


@pytest.mark.parametrize("page", CHECKBOX_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_the_selection_surface_is_gone_once_the_session_is_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """`ready` is open for responses; `expired` and `archived` are over.
    None of the three can accept a roster mutation, so none of them
    offers one."""
    s = _session(client, db, code=f"sl-off-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert f'class="{SELECT_CLASS[page]}"' not in body, "no row checkboxes"
    assert f'id="{page}-delete-btn"' not in body, "no Delete"
    assert f'id="{page}-edit-btn"' not in body, "no Edit"
    assert f'id="{page}-delete-confirm"' not in body, "no delete gate"
    assert f'id="{page}-bulk-form"' not in body, "no bulk form"


@pytest.mark.parametrize("page", CHECKBOX_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_reading_the_roster_still_works_when_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """The filter strip is read-only and stays. Hiding it would make a
    completed session's roster unsearchable for no safety gain."""
    s = _session(client, db, code=f"sl-read-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert '<select name="status">' in body, "the status filter"
    assert ">Search</button>" in body, "the search submit"


@pytest.mark.parametrize("status", FROZEN)
def test_the_observers_bulk_card_follows_the_same_gate(
    db: Session, client: TestClient, status: str
) -> None:
    s = _session(client, db, code=f"sl-obs-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    assert 'id="observers-delete-btn"' not in body
    assert 'id="observers-bulk-form"' not in body


@pytest.mark.parametrize("status", ("ready", "expired"))
def test_observers_keep_their_checkboxes_for_the_cohort_editor(
    db: Session, client: TestClient, status: str
) -> None:
    """The one deliberate exception. Observers' checkboxes drive the
    cohort rule editor, which is gated on `not archived` on purpose so
    it stays live mid-session — narrowing them to `is_editable` would
    break that surface to fix a different one."""
    s = _session(client, db, code=f"sl-cohort-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    # Pinned on the checkbox markup, not the bare class name: that name
    # also appears in the page's own `querySelectorAll(".observer-select")`,
    # which renders whatever the gate says — the 19H.1 trap, and a mutant
    # narrowing this gate walked straight through the looser assertion.
    assert '<input type="checkbox" class="observer-select"' in body, (
        "checkboxes stay for the rule editor"
    )


@pytest.mark.parametrize("page", ALL_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_the_route_still_refuses_even_though_the_page_no_longer_asks(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """The page is not the gate. Hiding a control is a courtesy; the
    409 is the guarantee, and it is unchanged."""
    s = _session(client, db, code=f"sl-post-{page}-{status}")
    model = {
        "reviewers": Reviewer,
        "reviewees": Reviewee,
        "observers": Observer,
        "relationships": Relationship,
    }[page]
    row_id = db.execute(
        select(model.id).where(model.session_id == s.id)
    ).scalars().first()
    s.status = status
    db.commit()

    field = {
        "reviewers": "reviewer_ids",
        "reviewees": "reviewee_ids",
        "observers": "observer_ids",
        "relationships": "relationship_ids",
    }[page]
    response = client.post(
        f"/operator/sessions/{s.id}/{page}/bulk-delete",
        data={field: [row_id], "confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 409, response.status_code
    assert db.get(model, row_id) is not None
