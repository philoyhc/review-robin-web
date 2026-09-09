"""Replacing a roster on a session that has responses — 19I Item 5.

Reported from use: an operator reverted an active session to draft to
fix its roster, uploaded a replacement CSV, and got **400 Bad request —
"Existing reviewer responses will be discarded; tick 'acknowledge
response loss' to proceed"**, with no such tick anywhere on the page.

The same defect the Danger Zone had (Item 3), on the import path: the
route requires `acknowledge_response_loss` and the upload form has
never sent it. Reverting to draft is the *correct* workflow for
editing a started session, so this is on the road an operator is
supposed to take.
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
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
)

CSV = {
    "reviewers": b"ReviewerName,ReviewerEmail\nNew Ann,newann@example.edu\n",
    "reviewees": b"RevieweeName,RevieweeEmail\nNew Bob,newbob@example.edu\n",
    "observers": b"ObserverEmail\nnewobs@example.edu\n",
}


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
    s.observers_enabled = True
    s.relationships_enabled = True
    db.commit()
    return s


def _roster_with_responses(db: Session, s: ReviewSession, *, n: int) -> None:
    """A started session's shape: a roster, an assignment, saved
    answers — then reverted to draft, which is where the operator is
    when they try to fix the roster."""
    from app.db.models import Observer

    reviewer = Reviewer(session_id=s.id, name="Old", email="old@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="Old E", email_or_identifier="olde@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.add(Observer(session_id=s.id, email="o@example.edu", display_name="O"))
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


def _upload_form(body: str, page: str) -> str:
    """The Upload card's `<form>` — the one whose opening tag posts to
    the import route.

    Found by walking the page's forms rather than by seeking the path,
    because the error render's chrome carries
    `?return_to=/operator/sessions/1/reviewers/import` in a header
    link that precedes every `<form>` on the page.
    """
    action = f'/{page}/import"'
    pos = 0
    while True:
        pos = body.index("<form", pos)
        close = body.index("</form>", pos)
        block = body[pos:close]
        if action in block[: block.index(">") + 1]:
            return block
        pos = close



@pytest.mark.parametrize("page", ("reviewers", "reviewees", "observers"))
def test_replacing_a_roster_works_on_a_session_that_has_responses(
    db: Session, client: TestClient, page: str
) -> None:
    """The reported defect. The test posts **exactly what the rendered
    form carries** — inventing a field the page does not offer would
    prove the route works while leaving the operator stuck."""
    s = _session(client, db, code=f"imp-{page}")
    _roster_with_responses(db, s, n=2)

    body = client.get(f"/operator/sessions/{s.id}/{page}").text
    form = _upload_form(body, page)

    data: dict[str, str] = {}
    if 'name="confirm_replace"' in form:
        data["confirm_replace"] = "true"
    if 'name="acknowledge_response_loss"' in form:
        data["acknowledge_response_loss"] = "true"

    response = client.post(
        f"/operator/sessions/{s.id}/{page}/import",
        files={"file": ("new.csv", CSV[page], "text/csv")},
        data=data,
        follow_redirects=False,
    )

    assert response.status_code in (200, 303), (
        page,
        response.status_code,
        response.text[:300],
    )


@pytest.mark.parametrize("page", ("reviewers", "reviewees"))
def test_the_upload_label_names_the_responses_it_will_discard(
    db: Session, client: TestClient, page: str
) -> None:
    s = _session(client, db, code=f"imp-copy-{page}")
    _roster_with_responses(db, s, n=3)

    form = _upload_form(client.get(f"/operator/sessions/{s.id}/{page}").text, page)

    assert "3 reviewer responses" in form


@pytest.mark.parametrize("page", ("reviewers", "reviewees"))
def test_the_label_names_no_responses_when_there_are_none(
    db: Session, client: TestClient, page: str
) -> None:
    s = _session(client, db, code=f"imp-bare-{page}")
    db.add(Reviewer(session_id=s.id, name="Old", email="old@example.edu"))
    db.add(
        Reviewee(
            session_id=s.id, name="Old E", email_or_identifier="olde@example.edu"
        )
    )
    db.commit()

    form = _upload_form(client.get(f"/operator/sessions/{s.id}/{page}").text, page)

    assert "reviewer response" not in form


def test_replacing_the_observer_roster_keeps_every_response(
    db: Session, client: TestClient
) -> None:
    """Observers reach no assignment and no response (Item 2), so the
    import must neither demand an acknowledgement nor destroy one."""
    s = _session(client, db, code="imp-obs-keeps")
    _roster_with_responses(db, s, n=4)

    response = client.post(
        f"/operator/sessions/{s.id}/observers/import",
        files={"file": ("new.csv", CSV["observers"], "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code in (200, 303), response.status_code
    assert len(db.execute(select(Response)).scalars().all()) == 4


@pytest.mark.parametrize("page", ("reviewers", "reviewees"))
def test_a_blocked_upload_redisplays_the_label_with_its_clause(
    db: Session, client: TestClient, page: str
) -> None:
    """The import handler's error render builds its own context, which
    is where `delete_discards_responses` went missing unnoticed (Item
    3). Pin the clause on that path, not only on the GET."""
    s = _session(client, db, code=f"imp-blocked-{page}")
    _roster_with_responses(db, s, n=2)

    response = client.post(
        f"/operator/sessions/{s.id}/{page}/import",
        files={"file": ("bad.csv", b"NotAColumn\nx\n", "text/csv")},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    form = _upload_form(response.text, page)
    assert "2 reviewer responses" in form
    assert 'name="acknowledge_response_loss"' in form
