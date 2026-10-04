"""Regression tests for service-layer commit boundaries.

The default integration ``db`` fixture wraps every request in a SAVEPOINT,
so a service that forgets to call ``db.commit()`` still appears to persist
data within the test session. Production routes don't get that safety —
each request opens its own connection and closes it without committing
if the service didn't commit explicitly. These tests run against a
``committed_engine`` / ``committed_client`` harness (see
``tests/integration/conftest.py``) that mirrors the production pattern,
so a missing commit shows up as a failed assertion rather than passing
silently.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ReviewSession,
)


def _bootstrap(
    committed_client: TestClient, committed_engine: Engine, *, code: str
) -> tuple[int, int]:
    """Create a session via the route, return (session_id, instrument_id)."""
    response = committed_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    with Session(committed_engine) as s:
        review_session = s.execute(
            select(ReviewSession).where(ReviewSession.code == code)
        ).scalar_one()
        instrument = s.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalar_one()
        return review_session.id, instrument.id


def test_add_display_field_route_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="add-disp"
    )

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/display-fields",
        data={
            "source_pair": "reviewee:tag_1",
            "label": "Cohort",
            "visible": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    with Session(committed_engine) as s:
        rows = s.execute(
            select(InstrumentDisplayField)
            .where(InstrumentDisplayField.instrument_id == instrument_id)
            .order_by(InstrumentDisplayField.order)
        ).scalars().all()
    # Locked Name + Email rows are seeded on session creation; the
    # newly-added tag_1 row appends at order 2.
    assert [(r.source_type, r.source_field, r.label) for r in rows] == [
        ("reviewee", "name", ""),
        ("reviewee", "email_or_identifier", ""),
        ("reviewee", "tag_1", "Cohort"),
    ]


def test_update_display_field_label_no_longer_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """Segment 15A Slice 2 regression pin: the per-instrument
    ``Friendly Label`` input on the Instruments page was retired;
    the ``POST /display-fields/{id}/edit`` endpoint no longer
    accepts the ``label`` form parameter. Any stray ``label`` in
    the payload is silently ignored — the column stays at its
    existing (empty) value in the schema."""
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="edit-disp"
    )
    committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/display-fields",
        data={"source_pair": "reviewee:tag_1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    with Session(committed_engine) as s:
        df_id = s.execute(
            select(InstrumentDisplayField.id).where(
                InstrumentDisplayField.instrument_id == instrument_id,
                InstrumentDisplayField.source_field == "tag_1",
            )
        ).scalar_one()

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/display-fields/{df_id}/edit",
        data={"label": "Cohort A", "visible": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    with Session(committed_engine) as s:
        df = s.get(InstrumentDisplayField, df_id)
        assert df is not None
        # Per Slice 2 retirement: the stray ``label`` field is
        # silently ignored. The DB column stays at its original
        # value (the empty seed from the add POST).
        assert df.label == ""


def test_delete_display_field_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="del-disp"
    )
    committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/display-fields",
        data={"source_pair": "reviewee:tag_1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    with Session(committed_engine) as s:
        df_id = s.execute(
            select(InstrumentDisplayField.id).where(
                InstrumentDisplayField.instrument_id == instrument_id,
                InstrumentDisplayField.source_field == "tag_1",
            )
        ).scalar_one()

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/display-fields/{df_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        # Locked Name + Email rows persist; only the operator-added
        # tag_1 row should be gone.
        sources = sorted(
            (r.source_type, r.source_field)
            for r in s.execute(
                select(InstrumentDisplayField).where(
                    InstrumentDisplayField.instrument_id == instrument_id
                )
            ).scalars()
        )
    assert sources == [
        ("reviewee", "email_or_identifier"),
        ("reviewee", "name"),
    ]


def test_delete_response_field_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """The other headline regression: clicking the ✗ on a Response Field
    actually deletes the row in the database."""
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="del-rf"
    )
    with Session(committed_engine) as s:
        comments = s.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument_id,
                InstrumentResponseField.field_key == "comments",
            )
        ).scalar_one()
        comments_id = comments.id

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/fields/{comments_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        gone = s.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.id == comments_id
            )
        ).scalar_one_or_none()
    assert gone is None


def test_update_response_field_label_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="edit-rf"
    )
    with Session(committed_engine) as s:
        rating = s.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument_id,
                InstrumentResponseField.field_key == "rating",
            )
        ).scalar_one()
        rating_id = rating.id

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/fields/{rating_id}/edit",
        data={
            "label": "Score",
            "required": "true",
            "validation_min": "1",
            "validation_max": "5",
            "help_text": "",
            "help_text_visible": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    with Session(committed_engine) as s:
        rf = s.get(InstrumentResponseField, rating_id)
        assert rf is not None
        assert rf.label == "Score"


def test_move_response_field_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="move-rf"
    )
    with Session(committed_engine) as s:
        rating = s.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == instrument_id,
                InstrumentResponseField.field_key == "rating",
            )
        ).scalar_one()
        rating_id = rating.id

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/fields/{rating_id}/move",
        data={"direction": "down"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        keys_in_order = [
            r.field_key
            for r in s.execute(
                select(InstrumentResponseField)
                .where(InstrumentResponseField.instrument_id == instrument_id)
                .order_by(InstrumentResponseField.order)
            ).scalars()
        ]
    assert keys_in_order == ["comments", "rating"]


def test_add_default_response_field_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="add-rf"
    )

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/add-row",
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        keys = sorted(
            r.field_key
            for r in s.execute(
                select(InstrumentResponseField).where(
                    InstrumentResponseField.instrument_id == instrument_id
                )
            ).scalars()
        )
    assert "rating3" in keys


def test_data_shapes_zip_all_audit_row_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """The Data shaper's Zip all (findings D13) commits its audit row;
    ``write_event`` alone only flushes."""
    from app.db.models import AuditEvent

    session_id, _ = _bootstrap(
        committed_client, committed_engine, code="zip-shapes-commit"
    )
    assert committed_client.post(
        f"/operator/sessions/{session_id}/extract-data/shapes",
        json={
            "name": "One",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name"],
        },
    ).status_code == 201
    response = committed_client.get(
        f"/operator/sessions/{session_id}/export/data_shapes_bundle.zip"
    )
    assert response.status_code == 200

    with Session(committed_engine) as s:
        assert s.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == session_id,
                AuditEvent.event_type == "session.data_shapes_bundle_extracted",
            )
        ).scalar_one() is not None


@pytest.mark.parametrize(
    ("path", "event_type"),
    [
        ("settings.csv", "session.settings_extracted"),
        ("reviewers.csv", "session.reviewers_extracted"),
        ("reviewees.csv", "session.reviewees_extracted"),
        ("relationships.csv", "session.relationships_extracted"),
        ("observers.csv", "session.observers_extracted"),
        ("participant_tokens.csv", "session.participant_tokens_extracted"),
        ("responses.csv", "session.responses_extracted"),
        ("bundle.zip", "session.setup_bundle_extracted"),
        ("responses_bundle.zip", "session.responses_bundle_extracted"),
        ("by_instrument_bundle.zip", "session.by_instrument_bundle_extracted"),
        ("reviewer_metadata.csv", "session.reviewer_metadata_extracted"),
        ("reviewee_metadata.csv", "session.reviewee_metadata_extracted"),
    ],
)
def test_extract_audit_rows_persist(
    committed_client: TestClient,
    committed_engine: Engine,
    path: str,
    event_type: str,
) -> None:
    """Every Extract download commits its audit row (findings D33,
    2026-10-03): ``write_event`` only flushes and ``get_db`` closes
    without committing, so none of these rows survived the request.
    ``audit_log.csv`` (sys-admin only) and ``data_shapes_bundle.zip``
    (covered above) are the two left out."""
    from app.db.models import AuditEvent

    session_id, _ = _bootstrap(
        committed_client,
        committed_engine,
        code=f"x-{path.replace('.', '-').replace('_', '-')}",
    )
    response = committed_client.get(
        f"/operator/sessions/{session_id}/export/{path}"
    )
    assert response.status_code == 200, response.text

    with Session(committed_engine) as s:
        assert s.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == session_id,
                AuditEvent.event_type == event_type,
            )
        ).scalar_one() is not None
