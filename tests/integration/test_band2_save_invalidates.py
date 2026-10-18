"""A Band 2 response-field save demotes a validated session (findings S1).

Every other instrument save invalidates validation and writes an audit
row; the response-field save path did neither, so a validated session
could reach Activate with a Response template generated from fields
that had since changed.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession

from ._public_id import public_id
from .test_instrument_builder_routes import _band2_rfs, _instrument, _make_session


def _post(client: TestClient, session_id: int, instrument_id: int, rfs: list[dict]):
    return client.post(
        f"/operator/sessions/{public_id(session_id)}/instruments/{instrument_id}/band2-state",
        json={"selected_display_keys": ["reviewee.name"], "response_fields": rfs},
    )


def _events(db: Session, session_id: int) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session_id)
            .where(AuditEvent.event_type == "instrument.response_fields_saved")
        ).scalars()
    )


def _validated(db: Session, review_session: ReviewSession) -> None:
    review_session.status = "validated"
    db.commit()


def _setup(client: TestClient, db: Session, code: str) -> tuple[ReviewSession, Instrument]:
    review_session = _make_session(client, db, code=code)
    instrument = _instrument(db, review_session.id)
    resp = _post(
        client,
        review_session.id,
        instrument.id,
        [
            {"name": "Rating", "data_type": "integer", "min": "1", "max": "5",
             "step": "1", "list_options": "", "selected": True},
            {"name": "Comments", "data_type": "string", "min": "", "max": "200",
             "step": "", "list_options": "", "selected": True},
        ],
    )
    assert resp.status_code == 200, resp.text
    db.refresh(instrument)
    return review_session, instrument


def test_changing_a_response_field_demotes_and_audits(
    client: TestClient, db: Session
) -> None:
    review_session, instrument = _setup(client, db, "s1-change")
    _validated(db, review_session)
    before = len(_events(db, review_session.id))

    rfs = _band2_rfs(instrument)
    rfs[0]["name"] = "Score"
    rfs[0]["max"] = "10"
    assert _post(client, review_session.id, instrument.id, rfs).status_code == 200

    db.refresh(review_session)
    assert review_session.status == "draft"
    events = _events(db, review_session.id)
    assert len(events) == before + 1
    changes = events[-1].detail["set_changes"]
    assert changes["added"] == [] and changes["removed"] == []
    (updated,) = changes["updated"]
    assert updated["changes"]["label"] == ["Rating", "Score"]
    assert updated["changes"]["inline_max"] == [5, 10]
    assert events[-1].detail["refs"]["instrument_id"] == instrument.id


def test_identical_resave_keeps_validation_and_writes_nothing(
    client: TestClient, db: Session
) -> None:
    review_session, instrument = _setup(client, db, "s1-same")
    _validated(db, review_session)
    before = len(_events(db, review_session.id))

    rfs = _band2_rfs(instrument)
    assert _post(client, review_session.id, instrument.id, rfs).status_code == 200

    db.refresh(review_session)
    assert review_session.status == "validated"
    assert len(_events(db, review_session.id)) == before


def test_removing_every_field_demotes(client: TestClient, db: Session) -> None:
    review_session, instrument = _setup(client, db, "s1-remove")
    _validated(db, review_session)

    assert _post(client, review_session.id, instrument.id, []).status_code == 200

    db.refresh(review_session)
    assert review_session.status == "draft"
    removed = _events(db, review_session.id)[-1].detail["set_changes"]["removed"]
    assert sorted(r["label"] for r in removed) == ["Comments", "Rating"]


def test_unchanged_save_of_a_seeded_instrument_keeps_validation(
    client: TestClient, db: Session
) -> None:
    """The seed numbers its fields from 1 and the sync from 0, so the
    rank is compared, not the stored ``order``."""
    review_session = _make_session(client, db, code="s1-seeded")
    instrument = _instrument(db, review_session.id)
    assert sorted(f.order for f in instrument.response_fields)[0] == 1
    _validated(db, review_session)
    before = len(_events(db, review_session.id))

    rfs = _band2_rfs(instrument)
    assert _post(client, review_session.id, instrument.id, rfs).status_code == 200

    db.refresh(review_session)
    assert review_session.status == "validated"
    assert len(_events(db, review_session.id)) == before


def test_reordering_demotes(client: TestClient, db: Session) -> None:
    review_session, instrument = _setup(client, db, "s1-reorder")
    _validated(db, review_session)

    rfs = list(reversed(_band2_rfs(instrument)))
    assert _post(client, review_session.id, instrument.id, rfs).status_code == 200

    db.refresh(review_session)
    assert review_session.status == "draft"
    updated = _events(db, review_session.id)[-1].detail["set_changes"]["updated"]
    assert {u["field_key"] for u in updated if "order" in u["changes"]} == {
        f.field_key for f in instrument.response_fields
    }
