"""A roster address bound to a directory account reads as a display pill
in the roster, Relationships, Assignments, Invitations and Responses
tables and their drill-ins (segment 19Z, author 2026-10-31);
an unbound address stays plain code."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Assignment, Observer, Relationship, Reviewee, Reviewer
from app.services.instruments import ensure_default_instrument

from .test_held_upload_setup_cards import _session

JANE = "11111111-1111-4111-8111-111111111111"
PILL = re.compile(r'<code class="pill pill-count pill-address" title="Matched to a directory account"[^>]*data-directory-matched[^>]*>([^<]+)</code>')


def _seed(client: TestClient, db: Session, code: str):
    s = _session(client, db, code=code)
    bound_r = Reviewer(session_id=s.id, name="Jane", email="e0123456@example.edu", directory_object_id=JANE)
    plain_r = Reviewer(session_id=s.id, name="Pat", email="pat@example.edu")
    bound_e = Reviewee(session_id=s.id, name="Jane", email_or_identifier="Jane.Tan@example.edu", directory_object_id=JANE)
    plain_e = Reviewee(session_id=s.id, name="Anon", email_or_identifier="STU-0001")
    db.add_all([bound_r, plain_r, bound_e, plain_e,
                Observer(session_id=s.id, email="e0123456@example.edu", directory_object_id=JANE),
                Observer(session_id=s.id, email="obs@example.edu")])
    db.flush()
    instrument = ensure_default_instrument(db, s)
    db.add(Assignment(session_id=s.id, reviewer_id=bound_r.id, reviewee_id=plain_e.id, instrument_id=instrument.id))
    db.add(Assignment(session_id=s.id, reviewer_id=plain_r.id, reviewee_id=bound_e.id, instrument_id=instrument.id))
    s.relationships_enabled = True
    db.add(Relationship(session_id=s.id, reviewer_id=bound_r.id, reviewee_id=plain_e.id))
    db.add(Relationship(session_id=s.id, reviewer_id=plain_r.id, reviewee_id=bound_e.id))
    db.commit()
    s.ids = {"bound_r": bound_r.id, "plain_r": plain_r.id, "bound_e": bound_e.id, "plain_e": plain_e.id}
    return s


@pytest.mark.parametrize(
    ("page", "bound", "plain"),
    [
        ("reviewers", "e0123456@example.edu", "pat@example.edu"),
        ("reviewees", "Jane.Tan@example.edu", "STU-0001"),
        ("observers", "e0123456@example.edu", "obs@example.edu"),
    ],
)
def test_a_bound_roster_address_is_a_pill_and_an_unbound_one_plain(
    client: TestClient, db: Session, page: str, bound: str, plain: str
) -> None:
    s = _seed(client, db, f"pill-{page}")
    html = client.get(f"/operator/sessions/{s.public_id}/{page}").text
    assert PILL.findall(html) == [bound]  # case kept, one pill
    assert f"<code>{plain}</code>" in html


def test_the_assignments_table_pills_bound_addresses_on_both_sides(client: TestClient, db: Session) -> None:
    s = _seed(client, db, "pill-assign")
    html = client.get(f"/operator/sessions/{s.public_id}/assignments").text
    assert sorted(PILL.findall(html)) == ["Jane.Tan@example.edu", "e0123456@example.edu"]
    assert "<code>pat@example.edu</code>" in html and "<code>STU-0001</code>" in html


@pytest.mark.parametrize("page", ["relationships", "invitations", "responses"])
def test_the_relationships_invitations_and_responses_tables_pill_bound_addresses(
    client: TestClient, db: Session, page: str
) -> None:
    s = _seed(client, db, f"pill-{page}")
    response = client.get(f"/operator/sessions/{s.public_id}/{page}")
    assert response.status_code == 200
    html = response.text
    expected = {
        "relationships": ["Jane.Tan@example.edu", "e0123456@example.edu"],
        "invitations": ["e0123456@example.edu"],
        "responses": ["Jane.Tan@example.edu"],
    }[page]
    assert sorted(PILL.findall(html)) == expected
    plain = {"relationships": "pat@example.edu", "invitations": "pat@example.edu", "responses": "STU-0001"}[page]
    assert f"<code>{plain}</code>" in html


@pytest.mark.parametrize(
    ("path", "bound"),
    [
        ("invitations/reviewers/{bound_r}", True),
        ("invitations/reviewers/{plain_r}", False),
        ("responses/{bound_e}/detail", True),
        ("responses/{plain_e}/detail", False),
    ],
)
def test_the_drill_in_headers_pill_a_bound_address(client: TestClient, db: Session, path: str, bound: bool) -> None:
    s = _seed(client, db, f"pill-d-{path.split('/')[0]}-{bound}")
    response = client.get(f"/operator/sessions/{s.public_id}/" + path.format(**s.ids))
    assert response.status_code == 200
    assert bool(PILL.findall(response.text)) is bound
