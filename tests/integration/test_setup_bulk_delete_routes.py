"""The four `bulk-delete` routes — Segment 19I Item 2 PR 3.

The service is unit-tested in `tests/unit/test_roster_bulk_delete.py`;
this is the route contract around it: the two gates, the lifecycle
gate, the redirect, and the one thing a service test structurally
cannot check — that the page hands the route the ids it was given.

The **client** gate (a selection enables the checkbox, the checkbox
enables the button) is a convenience. Every assertion here posts
directly, because the server check is the one that counts.
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
ID_FIELD = {
    "reviewers": "reviewer_ids",
    "reviewees": "reviewee_ids",
    "observers": "observer_ids",
    "relationships": "relationship_ids",
}


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.commit()
    return review_session


def _rows(db: Session, s: ReviewSession, page: str, n: int) -> list:
    """`n` rows of the page's own entity, plus whatever they need."""
    if page == "reviewers":
        rows = [
            Reviewer(session_id=s.id, name=f"R{i}", email=f"r{i}@example.edu")
            for i in range(n)
        ]
    elif page == "reviewees":
        rows = [
            Reviewee(
                session_id=s.id,
                name=f"E{i}",
                email_or_identifier=f"e{i}@example.edu",
            )
            for i in range(n)
        ]
    elif page == "observers":
        rows = [
            Observer(session_id=s.id, email=f"o{i}@example.edu", display_name=f"O{i}")
            for i in range(n)
        ]
    else:
        reviewers = [
            Reviewer(session_id=s.id, name=f"R{i}", email=f"pr{i}@example.edu")
            for i in range(n)
        ]
        reviewee = Reviewee(
            session_id=s.id, name="Solo", email_or_identifier="solo@example.edu"
        )
        db.add_all([*reviewers, reviewee])
        db.flush()
        rows = [
            Relationship(
                session_id=s.id, reviewer_id=r.id, reviewee_id=reviewee.id
            )
            for r in reviewers
        ]
    db.add_all(rows)
    db.commit()
    return rows


def _with_responses(
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
    assignment = Assignment(
        session_id=s.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="manual",
    )
    db.add(assignment)
    db.flush()
    for i, field in enumerate(fields):
        db.add(
            Response(
                assignment_id=assignment.id,
                response_field_id=field.id,
                value=str(i),
                saved_at=_dt.datetime(2026, 9, 9, tzinfo=_dt.timezone.utc),
                version=1,
            )
        )
    db.commit()


def _post(client: TestClient, s: ReviewSession, page: str, **data):
    return client.post(
        f"/operator/sessions/{s.id}/{page}/bulk-delete",
        data=data,
        follow_redirects=False,
    )


# ── The happy path ─────────────────────────────────────────────────────


@pytest.mark.parametrize("page", PAGES)
def test_a_confirmed_post_deletes_only_the_selected_rows(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"bdr-ok-{page}")
    rows = _rows(db, s, page, 3)
    doomed = [rows[0].id, rows[2].id]
    survivor = rows[1].id
    model = type(rows[0])

    response = _post(
        client, s, page, **{ID_FIELD[page]: doomed}, confirm="true"
    )

    assert response.status_code == 303, response.text
    left = db.execute(
        select(model.id).where(model.session_id == s.id)
    ).scalars().all()
    assert left == [survivor]


@pytest.mark.parametrize("page", PAGES)
def test_the_redirect_keeps_the_filters_and_carries_no_selection(
    db: Session, client: TestClient, page: str
) -> None:
    """The deleted rows cannot be re-checked, so unlike every other
    bulk action this redirect carries no `selected=`."""
    s = _make_session(client, db, code=f"bdr-redir-{page}")
    rows = _rows(db, s, page, 2)

    response = _post(
        client,
        s,
        page,
        **{ID_FIELD[page]: [rows[0].id]},
        confirm="true",
        filter_status="inactive",
        filter_q="Ana",
    )

    location = response.headers["location"]
    assert "status=inactive" in location
    assert "q=Ana" in location
    assert "selected=" not in location


# ── The gates ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("page", PAGES)
def test_an_unconfirmed_post_is_refused_and_deletes_nothing(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"bdr-noconf-{page}")
    rows = _rows(db, s, page, 2)
    model = type(rows[0])

    response = _post(client, s, page, **{ID_FIELD[page]: [rows[0].id]})

    assert response.status_code == 400
    assert (
        len(
            db.execute(select(model).where(model.session_id == s.id))
            .scalars()
            .all()
        )
        == 2
    ), "a refused post must not have deleted anything"


@pytest.mark.parametrize("page", PAGES)
def test_confirm_must_be_exactly_true(
    db: Session, client: TestClient, page: str
) -> None:
    """A checkbox posts `value="true"`; anything else is not a tick."""
    s = _make_session(client, db, code=f"bdr-conf-{page}")
    rows = _rows(db, s, page, 1)

    assert (
        _post(
            client, s, page, **{ID_FIELD[page]: [rows[0].id]}, confirm="on"
        ).status_code
        == 400
    )


def test_responses_on_the_selected_rows_need_acknowledgement(
    db: Session, client: TestClient
) -> None:
    s = _make_session(client, db, code="bdr-ack")
    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    _with_responses(db, s, reviewer=reviewer, reviewee=reviewee, n=3)

    refused = _post(
        client, s, "reviewers", reviewer_ids=[reviewer.id], confirm="true"
    )
    assert refused.status_code == 400
    assert "3 saved responses" in refused.text, refused.text
    assert db.get(Reviewer, reviewer.id) is not None

    allowed = _post(
        client,
        s,
        "reviewers",
        reviewer_ids=[reviewer.id],
        confirm="true",
        acknowledge_response_loss="true",
    )
    assert allowed.status_code == 303
    assert db.get(Reviewer, reviewer.id) is None
    assert db.execute(select(Response)).scalars().all() == []


def test_the_gate_counts_the_selection_not_the_session(
    db: Session, client: TestClient
) -> None:
    """The session has responses; the *selected* reviewer has none, so
    the delete goes through unacknowledged. A session-wide check —
    which is all `delete-all` can do — would refuse this."""
    s = _make_session(client, db, code="bdr-scope")
    answered = Reviewer(session_id=s.id, name="A", email="a@example.edu")
    clean = Reviewer(session_id=s.id, name="C", email="c@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([answered, clean, reviewee])
    db.flush()
    _with_responses(db, s, reviewer=answered, reviewee=reviewee, n=2)

    response = _post(
        client, s, "reviewers", reviewer_ids=[clean.id], confirm="true"
    )

    assert response.status_code == 303, response.text
    assert db.get(Reviewer, clean.id) is None
    assert db.get(Reviewer, answered.id) is not None
    assert len(db.execute(select(Response)).scalars().all()) == 2


@pytest.mark.parametrize("page", ["observers", "relationships"])
def test_observers_and_relationships_never_need_the_acknowledgement(
    db: Session, client: TestClient, page: str
) -> None:
    """PR 2 established these destroy no responses. The gate is not
    special-cased off for them — it simply never fires, because their
    cascade count is zero."""
    s = _make_session(client, db, code=f"bdr-noack-{page}")
    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    _with_responses(db, s, reviewer=reviewer, reviewee=reviewee, n=4)
    row = (
        Observer(session_id=s.id, email="o@example.edu", display_name="O")
        if page == "observers"
        else Relationship(
            session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        )
    )
    db.add(row)
    db.commit()

    response = _post(client, s, page, **{ID_FIELD[page]: [row.id]}, confirm="true")

    assert response.status_code == 303, response.text
    assert len(db.execute(select(Response)).scalars().all()) == 4


@pytest.mark.parametrize("page", PAGES)
def test_an_id_from_another_session_is_refused(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"bdr-cross-{page}")
    other = _make_session(client, db, code=f"bdr-other-{page}")
    mine = _rows(db, s, page, 1)[0]
    stranger = _rows(db, other, page, 1)[0]
    model = type(mine)

    response = _post(
        client,
        s,
        page,
        **{ID_FIELD[page]: [mine.id, stranger.id]},
        confirm="true",
    )

    assert response.status_code == 400
    assert db.get(model, mine.id) is not None, "the valid id survives too"


@pytest.mark.parametrize("page", PAGES)
def test_a_non_editable_session_refuses(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"bdr-locked-{page}")
    rows = _rows(db, s, page, 1)
    s.status = "ready"
    db.commit()

    response = _post(
        client, s, page, **{ID_FIELD[page]: [rows[0].id]}, confirm="true"
    )

    assert response.status_code in (400, 409), response.status_code
    assert db.get(type(rows[0]), rows[0].id) is not None


# ── The acknowledgement checkbox ───────────────────────────────────────


@pytest.mark.parametrize("page", ["reviewers", "reviewees"])
def test_the_gate_names_the_response_loss_when_there_is_any(
    db: Session, client: TestClient, page: str
) -> None:
    s = _make_session(client, db, code=f"bdr-ackbox-{page}")
    _rows(db, s, page, 1)

    without = client.get(f"/operator/sessions/{s.id}/{page}").text
    assert f'id="{page}-delete-ack"' not in without

    reviewer = Reviewer(session_id=s.id, name="Z", email="z@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="Y", email_or_identifier="y@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    _with_responses(db, s, reviewer=reviewer, reviewee=reviewee, n=1)

    with_loss = client.get(f"/operator/sessions/{s.id}/{page}").text
    assert f'id="{page}-delete-ack"' in with_loss
    assert "delete these and discard their saved responses" in with_loss, (
        "one gate, and its label says what the tick agrees to"
    )


@pytest.mark.parametrize("page", ["observers", "relationships"])
def test_the_gate_never_names_response_loss_where_there_is_none(
    db: Session, client: TestClient, page: str
) -> None:
    """Even on a session full of responses. Deleting an observer or a
    pair-context row destroys none of them (PR 2), and a checkbox
    offering to discard responses would be telling the operator
    something untrue about what the button does."""
    s = _make_session(client, db, code=f"bdr-noackbox-{page}")
    _rows(db, s, page, 1)
    reviewer = Reviewer(session_id=s.id, name="Z", email="z@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="Y", email_or_identifier="y@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    _with_responses(db, s, reviewer=reviewer, reviewee=reviewee, n=2)

    body = client.get(f"/operator/sessions/{s.id}/{page}").text

    assert f'id="{page}-delete-ack"' not in body
    assert "discard their saved responses" not in body
