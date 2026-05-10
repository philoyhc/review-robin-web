from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField, ReviewSession
from ._full_matrix import full_matrix_seed_id


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Test", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_session_creation_yields_default_instrument_with_seed_fields(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="invariant-test")

    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    assert len(instruments) == 1
    instrument = instruments[0]
    assert instrument.name == "Default"
    assert instrument.order == 0

    fields = list(
        db.execute(
            select(InstrumentResponseField)
            .where(InstrumentResponseField.instrument_id == instrument.id)
            .order_by(InstrumentResponseField.order)
        ).scalars()
    )
    assert len(fields) == 2

    rating, comments = fields
    assert rating.field_key == "rating"
    assert rating.response_type == "1-to-5int"
    assert rating.data_type == "Integer"
    assert rating.required is True
    assert rating.validation == {"min": 1, "max": 5, "step": 1}
    assert rating.order == 1

    assert comments.field_key == "comments"
    assert comments.response_type == "Long_text"
    assert comments.data_type == "String"
    assert comments.required is False
    assert comments.validation == {"min_length": 0, "max_length": 2000}
    assert comments.order == 2


def test_assignment_generation_reuses_existing_default_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="reuse-test")
    initial_instrument_id = db.execute(
        select(Instrument.id).where(Instrument.session_id == review_session.id)
    ).scalar_one()

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": "true"},
        follow_redirects=False,
    )

    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    assert len(instruments) == 1
    assert instruments[0].id == initial_instrument_id
