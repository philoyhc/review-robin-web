"""Segment 20B rung 2: the ``symmetric_review`` setting.

It is stored on create, toggled on Session Home's details card, and
carried by the Settings CSV and a clone. It turns on only while both
rosters are empty; turning it off is always allowed and clears the
mirror links. While it is on, the Reviewees page is read-only and its
Quick Setup slot greyed. The mirror itself is rung 3's.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Reviewee, Reviewer, ReviewSession
from app.services import session_config_io


def _make_session(client: TestClient, db: Session, code: str, **form: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Sym", "code": code, "description": "", **form},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _save(client: TestClient, review_session: ReviewSession, **form: str) -> None:
    response = client.post(
        f"/operator/sessions/{review_session.public_id}/config",
        data={
            "name": review_session.name,
            "code": review_session.code,
            "display_timezone": review_session.display_timezone or "UTC",
            **form,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _add_reviewer(db: Session, review_session: ReviewSession) -> Reviewer:
    reviewer = Reviewer(session_id=review_session.id, name="Ann", email="ann@example.edu")
    db.add(reviewer)
    db.commit()
    return reviewer


def test_create_stores_the_setting(client: TestClient, db: Session) -> None:
    assert _make_session(client, db, "sym-create", symmetric_review="true").symmetric_review is True
    assert _make_session(client, db, "sym-create-off").symmetric_review is False


def test_it_turns_on_only_while_both_rosters_are_empty(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-on")
    _add_reviewer(db, review_session)
    _save(client, review_session, symmetric_review="true")
    db.refresh(review_session)
    assert review_session.symmetric_review is False

    empty = _make_session(client, db, "sym-on-empty")
    _save(client, empty, symmetric_review="true")
    db.refresh(empty)
    assert empty.symmetric_review is True
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.feature_toggled",
            AuditEvent.session_id == empty.id,
        )
    ).scalars().all()
    assert any("symmetric_review" in str(e.detail) for e in events)


def test_off_is_always_allowed_and_clears_the_links(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-off", symmetric_review="true")
    reviewer = _add_reviewer(db, review_session)
    db.add(Reviewee(
        session_id=review_session.id, name="Ann", email_or_identifier="ann@example.edu",
        mirrors_reviewer_id=reviewer.id,
    ))
    db.commit()
    _save(client, review_session)
    db.refresh(review_session)
    assert review_session.symmetric_review is False
    reviewee = db.execute(select(Reviewee).where(Reviewee.session_id == review_session.id)).scalar_one()
    db.refresh(reviewee)
    assert reviewee.mirrors_reviewer_id is None


def _home_box(body: str) -> tuple[str, str]:
    """The Symmetric review chip's label tag and its input tag."""
    at = body.index('name="symmetric_review"')
    label = body[body.rindex("<label", 0, at):body.index(">", body.rindex("<label", 0, at))]
    box = body[body.rindex("<input", 0, at):body.index(">", at)]
    return label, box


def test_the_home_box_is_fixed_off_once_a_roster_has_rows(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-home")
    path = f"/operator/sessions/{review_session.public_id}?editing=1"
    label, box = _home_box(client.get(path).text)
    assert "is-fixed" not in label and "disabled" not in box
    _add_reviewer(db, review_session)
    label, box = _home_box(client.get(path).text)
    assert "is-fixed" in label and "disabled" in box


def test_on_greys_the_reviewees_slot_and_locks_the_page(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-ui", symmetric_review="true")
    base = f"/operator/sessions/{review_session.public_id}"
    home = client.get(base).text
    slot = home[home.find('id="quick-setup-reviewees"'):]
    slot = slot[: slot.find("</section>")]
    assert "data-symmetric-mirrored" in slot and 'name="reviewees_file"' not in slot
    page = client.get(f"{base}/reviewees").text
    assert "data-symmetric-mirrored" in page
    for gone in ('id="roster-unlock-btn"', 'id="upload-csv"', 'id="reviewees-bulk-form"'):
        assert gone not in page, gone


def test_off_leaves_the_pages_as_they_were(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-plain")
    base = f"/operator/sessions/{review_session.public_id}"
    assert "data-symmetric-mirrored" not in client.get(base).text
    page = client.get(f"{base}/reviewees").text
    assert "data-symmetric-mirrored" not in page and 'id="roster-unlock-btn"' in page


def test_new_session_ticks_grey_the_slot_in_the_browser(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text
    card = body[body.find('id="user-interface-settings"'):]
    box = card.find('name="symmetric_review"')
    assert box != -1 and box < card.find("Symmetric review\n")
    slot = body[body.find('id="quick-setup-reviewees"'):]
    assert "data-symmetric-reason hidden" in slot[: slot.find("</section>")]
    assert "[data-symmetric-reason]" in body


def test_the_settings_csv_carries_it(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, "sym-csv", symmetric_review="true")
    rows = session_config_io.serialize_session_config(db, review_session)
    assert any(r.field == "session.symmetric_review" and r.value == "true" for r in rows)

    target = _make_session(client, db, "sym-csv-target")
    session_config_io.apply_session_config(db, target, rows)
    db.commit()
    db.refresh(target)
    assert target.symmetric_review is True


def test_a_settings_csv_cannot_turn_it_on_beside_rows(client: TestClient, db: Session) -> None:
    source = _make_session(client, db, "sym-csv-src", symmetric_review="true")
    rows = session_config_io.serialize_session_config(db, source)
    target = _make_session(client, db, "sym-csv-rows")
    _add_reviewer(db, target)
    session_config_io.apply_session_config(db, target, rows)
    db.commit()
    db.refresh(target)
    assert target.symmetric_review is False
