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

from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    ReviewSession,
)


def _verify(committed_engine: Engine) -> Iterator[Session]:
    """Yield a fresh Session bound to the committed engine. Use to
    assert state was actually committed (not just flushed)."""
    with Session(committed_engine) as s:
        yield s


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
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument_id
            )
        ).scalars().all()
    assert [(r.source_type, r.source_field, r.label) for r in rows] == [
        ("reviewee", "tag_1", "Cohort"),
    ]


def test_update_display_field_label_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """The headline regression: the operator types a Friendly Label,
    clicks ✓, navigates away and back — and the value sticks."""
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
                InstrumentDisplayField.instrument_id == instrument_id
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
        assert df.label == "Cohort A"


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
                InstrumentDisplayField.instrument_id == instrument_id
            )
        ).scalar_one()

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}"
        f"/display-fields/{df_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        rows = s.execute(
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument_id
            )
        ).scalars().all()
    assert rows == []


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


def test_bulk_save_fields_label_persists(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="bulk-save"
    )
    committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/display-fields",
        data={"source_pair": "reviewee:tag_1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    with Session(committed_engine) as s:
        df_id = s.execute(
            select(InstrumentDisplayField.id).where(
                InstrumentDisplayField.instrument_id == instrument_id
            )
        ).scalar_one()
        rating_id = s.execute(
            select(InstrumentResponseField.id).where(
                InstrumentResponseField.instrument_id == instrument_id,
                InstrumentResponseField.field_key == "rating",
            )
        ).scalar_one()

    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/save",
        data={
            "kind": ["display", "response"],
            "id": [str(df_id), str(rating_id)],
            "order": ["0", "1"],
            "label": ["BulkLabel", ""],
            "visible_ids": [str(df_id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        df = s.get(InstrumentDisplayField, df_id)
        assert df is not None
        assert df.label == "BulkLabel"
