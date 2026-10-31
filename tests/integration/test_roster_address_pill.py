"""A roster address bound to a directory account reads as a display pill
in the roster and Assignments tables (segment 19Z, author 2026-10-31);
an unbound address stays plain code."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Assignment, Observer, Reviewee, Reviewer
from app.services.instruments import ensure_default_instrument

from .test_held_upload_setup_cards import _session

JANE = "11111111-1111-4111-8111-111111111111"
PILL = re.compile(r'<code class="pill pill-count pill-address"[^>]*data-directory-matched[^>]*>([^<]+)</code>')


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
    db.commit()
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
