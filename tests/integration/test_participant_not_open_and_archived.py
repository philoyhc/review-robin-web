"""The pre-open page's copy (participant audit M3) and archived
sessions being off limits to participants (M4, author's rulings of
2026-10-15 and 2026-10-16 in `guide/participant_surface_check.md`)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewer, ReviewSession

ALICE_EMAIL = "alice@example.edu"


def _session(
    client: TestClient, db: Session, *, code: str, status: str
) -> ReviewSession:
    """A session with the signed-in operator (Alice) also on its
    reviewer and observer rosters."""
    resp = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.status = status
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id, name="Alice", email=ALICE_EMAIL
            ),
            Observer(
                session_id=review_session.id,
                email=ALICE_EMAIL,
                display_name="Alice",
            ),
        ]
    )
    db.commit()
    return review_session


@pytest.mark.parametrize("status", ["draft", "validated"])
def test_every_not_open_state_reads_the_same(
    client: TestClient, db: Session, status: str
) -> None:
    review_session = _session(client, db, code=f"no-{status}", status=status)
    body = client.get(f"/me/sessions/{review_session.id}/1").text
    assert "This review is not currently open." in body
    # One name for the dashboard (participant audit L1).
    assert '<a class="btn secondary" href="/me">Your reviews</a>' in body
    for old in ("opens later", "has prepared the review", "has archived"):
        assert old not in body, old


def test_a_prepared_session_shows_when_it_is_scheduled_to_open(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, code="no-sched", status="validated")
    review_session.scheduled_activate_at = datetime(
        2031, 3, 4, 9, 30, tzinfo=timezone.utc
    )
    db.commit()
    body = client.get(f"/me/sessions/{review_session.id}/1").text
    assert "data-pre-open-scheduled" in body
    assert "2031-03-04 09:30" in body


def test_a_draft_shows_no_schedule(client: TestClient, db: Session) -> None:
    """A draft can't open on its schedule until it is prepared again."""
    review_session = _session(client, db, code="no-sched-draft", status="draft")
    review_session.scheduled_activate_at = datetime(
        2031, 3, 4, 9, 30, tzinfo=timezone.utc
    )
    db.commit()
    body = client.get(f"/me/sessions/{review_session.id}/1").text
    assert "data-pre-open-scheduled" not in body


@pytest.mark.parametrize("status", ["draft", "validated"])
def test_the_help_contact_shows(
    client: TestClient, db: Session, status: str
) -> None:
    review_session = _session(client, db, code=f"no-help-{status}", status=status)
    review_session.help_contact = "help@example.edu"
    db.commit()
    body = client.get(f"/me/sessions/{review_session.id}/1").text
    assert "Questions? Contact help@example.edu" in body


@pytest.mark.parametrize(
    "path",
    ["1", "summary", "summary.csv", "collation", "results"],
)
def test_an_archived_session_is_off_limits(
    client: TestClient, db: Session, path: str
) -> None:
    review_session = _session(client, db, code=f"arch-{path}", status="archived")
    resp = client.get(
        f"/me/sessions/{review_session.id}/{path}", follow_redirects=False
    )
    assert resp.status_code == 404


def test_collation_still_answers_before_archive(
    client: TestClient, db: Session
) -> None:
    """The 404 is archive's, not the observer gate's or the roster's."""
    review_session = _session(client, db, code="arch-before", status="expired")
    resp = client.get(f"/me/sessions/{review_session.id}/collation")
    assert resp.status_code == 200


def test_a_write_to_an_archived_session_is_refused_like_a_strangers(
    client: TestClient, db: Session
) -> None:
    """Save on an archived session is the gate's bare 404, not the
    refused-write page (that one names the session)."""
    review_session = _session(client, db, code="arch-save", status="archived")
    resp = client.post(
        f"/me/sessions/{review_session.id}/1/save", data={}, follow_redirects=False
    )
    assert resp.status_code == 404
    assert "Spring" not in resp.text


def test_the_surface_still_answers_before_archive(
    client: TestClient, db: Session
) -> None:
    review_session = _session(client, db, code="arch-surf-before", status="expired")
    assert client.get(f"/me/sessions/{review_session.id}/1").status_code == 200


def test_an_archived_session_names_no_role_on_the_guide(
    client: TestClient, db: Session, make_client
) -> None:
    """A participant whose only session is archived holds no role there
    (``participants.disclosable_roles``), so the Guide bounces them to
    About like any other signed-in stranger."""
    from app.auth.identity import AuthenticatedUser
    from app.services import participants

    pat = AuthenticatedUser(
        principal_id="pat-oid", email="pat@example.edu", name="Pat", provider="aad"
    )
    review_session = _session(client, db, code="arch-guide", status="ready")
    db.add(Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu"))
    db.commit()
    assert participants.disclosable_roles(db, "pat@example.edu")
    assert make_client(pat).get("/guide", follow_redirects=False).status_code == 200

    review_session.status = "archived"
    db.commit()
    assert participants.disclosable_roles(db, "pat@example.edu") == frozenset()
    resp = make_client(pat).get("/guide", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert resp.headers["location"].startswith("/about")


def test_a_back_link_does_not_name_an_archived_session(
    client: TestClient, db: Session, make_client
) -> None:
    from app.auth.identity import AuthenticatedUser

    pat = AuthenticatedUser(
        principal_id="pat-oid", email="pat@example.edu", name="Pat", provider="aad"
    )
    review_session = _session(client, db, code="arch-back", status="ready")
    review_session.name = "Secret Spring"
    db.add(Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu"))
    db.commit()
    path = f"/about?return_to=/me/sessions/{review_session.id}"
    assert "Back to Secret Spring" in make_client(pat).get(path).text

    review_session.status = "archived"
    db.commit()
    assert "Secret Spring" not in make_client(pat).get(path).text
