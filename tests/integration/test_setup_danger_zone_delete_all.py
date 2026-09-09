"""The Danger Zone's Delete-all — Segment 19I Item 3 PR 2.

`delete-all` has called `_require_response_loss_ack` since it was
written, and **no roster template ever sent the field**. So on any
session carrying a response the Danger Zone returned 400 with no path
forward from the page — found while wiring Item 2 PR 3, reported then,
and fixed here at the author's direction: "Danger needs to be able to
delete a session with responses."

The acknowledgement now rides with the same single tick the
selected-rows gate uses, and the label names what goes, modelled on the
Instruments page's sentence.
"""
from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Observer,
    Relationship,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)

PAGES = ("reviewers", "reviewees", "observers", "relationships")
# The two whose rows reach an assignment, and so a response.
CASCADING = ("reviewers", "reviewees")


def _session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.relationships_enabled = True
    s.observers_enabled = True
    db.commit()
    return s


def _roster(db: Session, s: ReviewSession) -> tuple[Reviewer, Reviewee]:
    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(Observer(session_id=s.id, email="o@example.edu", display_name="O"))
    db.add(
        Relationship(
            session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        )
    )
    db.commit()
    return reviewer, reviewee


def _responses(
    db: Session, s: ReviewSession, *, reviewer: Reviewer, reviewee: Reviewee, n: int
) -> None:
    instrument = Instrument(session_id=s.id, name="I", order=0)
    db.add(instrument)
    db.flush()
    fields = [
        InstrumentResponseField(
            instrument_id=instrument.id,
            field_key=f"f{i}",
            label=f"F{i}",
            _inline_data_type="Integer",
            _inline_response_type="Likert5",
            order=i,
        )
        for i in range(n)
    ]
    db.add_all(fields)
    a = Assignment(
        session_id=s.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(a)
    db.flush()
    for i, f in enumerate(fields):
        db.add(
            Response(
                assignment_id=a.id,
                response_field_id=f.id,
                value=str(i),
                saved_at=_dt.datetime(2026, 9, 9, tzinfo=_dt.timezone.utc),
                version=1,
            )
        )
    db.commit()


def _form_fields(body: str, page: str) -> str:
    """The Danger Zone form's markup for this page."""
    action = f'/{page}/delete-all"'
    start = body.rindex("<form", 0, body.index(action))
    return body[start : body.index("</form>", start)]


# ── The defect that opened the item ────────────────────────────────────


@pytest.mark.parametrize("page", PAGES)
def test_delete_all_works_on_a_session_that_has_responses(
    db: Session, client: TestClient, page: str
) -> None:
    """Before this PR every one of these returned 400, because the
    route wanted a field no template sent."""
    s = _session(client, db, code=f"dz-{page}")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=2)

    body = client.get(f"/operator/sessions/{s.id}/{page}").text
    form = _form_fields(body, page)

    # Post exactly what the rendered form carries — no invented fields.
    data: dict[str, str] = {"confirm": "true"}
    if 'name="acknowledge_response_loss"' in form:
        data["acknowledge_response_loss"] = "true"

    response = client.post(
        f"/operator/sessions/{s.id}/{page}/delete-all",
        data=data,
        follow_redirects=False,
    )

    assert response.status_code == 303, (page, response.status_code, response.text[:400])


@pytest.mark.parametrize("page", CASCADING)
def test_the_form_carries_the_acknowledgement_only_when_there_is_loss(
    db: Session, client: TestClient, page: str
) -> None:
    s = _session(client, db, code=f"dz-ack-{page}")
    reviewer, reviewee = _roster(db, s)

    clean = _form_fields(client.get(f"/operator/sessions/{s.id}/{page}").text, page)
    assert 'name="acknowledge_response_loss"' not in clean

    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=1)
    loaded = _form_fields(client.get(f"/operator/sessions/{s.id}/{page}").text, page)
    assert 'name="acknowledge_response_loss"' in loaded


def test_the_route_still_refuses_an_unacknowledged_post(
    db: Session, client: TestClient
) -> None:
    """The hidden field is the page's convenience, not a weakening of
    the gate: post without it and the 400 still stands."""
    s = _session(client, db, code="dz-refuse")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=1)

    response = client.post(
        f"/operator/sessions/{s.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert db.execute(select(Reviewer)).scalars().all()


# ── The copy ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("page", CASCADING)
def test_the_label_names_assignments_and_responses_when_they_exist(
    db: Session, client: TestClient, page: str
) -> None:
    s = _session(client, db, code=f"dz-copy-{page}")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=3)

    form = _form_fields(client.get(f"/operator/sessions/{s.id}/{page}").text, page)

    assert "their associated" in form
    assert "1 assignment" in form
    assert "3 reviewer responses" in form


@pytest.mark.parametrize("page", CASCADING)
def test_the_label_names_neither_on_a_bare_roster(
    db: Session, client: TestClient, page: str
) -> None:
    s = _session(client, db, code=f"dz-bare-{page}")
    _roster(db, s)

    form = _form_fields(client.get(f"/operator/sessions/{s.id}/{page}").text, page)

    assert "assignment" not in form
    assert "reviewer response" not in form


@pytest.mark.parametrize("page", ("observers", "relationships"))
def test_the_label_never_names_responses_where_none_can_be_lost(
    db: Session, client: TestClient, page: str
) -> None:
    """Even on a session full of them. Deleting these rosters reaches no
    assignment and no response (Item 2, from the model graph), so the
    Danger Zone must not imply otherwise."""
    s = _session(client, db, code=f"dz-none-{page}")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=4)

    form = _form_fields(client.get(f"/operator/sessions/{s.id}/{page}").text, page)

    assert "reviewer response" not in form
    assert "acknowledge_response_loss" not in form
    assert len(db.execute(select(Response)).scalars().all()) == 4


def test_deleting_the_observer_roster_leaves_every_response(
    db: Session, client: TestClient
) -> None:
    """The gate was dropped from this route rather than satisfied with a
    hidden field, because there is no loss to acknowledge. Asserted from
    behavior, not from the route's signature."""
    s = _session(client, db, code="dz-obs-keeps")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=4)

    response = client.post(
        f"/operator/sessions/{s.id}/observers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.execute(select(Observer)).scalars().all() == []
    assert len(db.execute(select(Response)).scalars().all()) == 4


# ── The second render path ─────────────────────────────────────────────


@pytest.mark.parametrize("page", CASCADING)
def test_the_csv_import_error_page_renders_the_same_strip(
    db: Session, client: TestClient, page: str
) -> None:
    """`_shared.py` builds its own context for the import-error render,
    so every key the strip reads has to be repeated there.
    `delete_discards_responses` was **missing since Item 2 PR 3 and
    nothing failed** — Jinja's `Undefined` is falsy in `{% if %}`, so
    the label quietly took its no-loss branch on this page. Only this
    PR's numeric comparison raised. Pinned so the next key added to the
    strip is not lost the same way."""
    s = _session(client, db, code=f"dz-import-{page}")
    reviewer, reviewee = _roster(db, s)
    _responses(db, s, reviewer=reviewer, reviewee=reviewee, n=2)

    # A CSV whose header is wrong enough to fail validation and
    # re-render the page with its issue list.
    response = client.post(
        f"/operator/sessions/{s.id}/{page}/import",
        files={"file": ("bad.csv", b"NotAColumn\nvalue\n", "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 400, response.status_code
    body = response.text
    # The strip rendered, and its label took the branch the data calls
    # for rather than the silent default.
    assert "their associated assignments and reviewer responses" in body
    form = _form_fields(body, page)
    assert 'name="acknowledge_response_loss"' in form
