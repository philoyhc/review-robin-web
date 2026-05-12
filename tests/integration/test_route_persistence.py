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


def test_bulk_save_fields_response_label_persists_display_label_retired(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """Segment 15A Slice 2: bulk-save still applies ``label`` to
    Response Fields (per-instrument question text — stays
    editable) but silently drops ``label`` for Display Fields
    (per-instrument override retired)."""
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
                InstrumentDisplayField.instrument_id == instrument_id,
                InstrumentDisplayField.source_field == "tag_1",
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
            "label": ["BulkLabel", "Renamed Rating"],
            "visible_ids": [str(df_id)],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    with Session(committed_engine) as s:
        df = s.get(InstrumentDisplayField, df_id)
        assert df is not None
        # Display Field label retired in 15A Slice 2 — the
        # ``BulkLabel`` value in the payload is silently dropped.
        assert df.label == ""
        rating = s.get(InstrumentResponseField, rating_id)
        assert rating is not None
        # Response Field label is still per-instrument question
        # text — stays editable.
        assert rating.label == "Renamed Rating"


def test_bulk_save_emits_aligned_arrays_when_display_label_input_retired(
    committed_client: TestClient, committed_engine: Engine
) -> None:
    """Regression pin: after 15A Slice 2 dropped the visible
    ``name="label"`` input from display rows, the rendered
    ``dfsave-{instrument.id}`` form must still submit a hidden
    empty ``label`` per display row so the route's parallel-
    array length check (``kinds / raw_ids / orders / labels``)
    stays balanced when display + response rows are submitted
    together.

    Renders the live ``?editing={iid}`` page, scrapes the form's
    input arrays straight from the HTML, and POSTs them at the
    bulk-save route. A 303 redirect means the alignment check
    passed; a 400 reproduces the original bug.
    """
    session_id, instrument_id = _bootstrap(
        committed_client, committed_engine, code="bulk-align"
    )
    # Seed an extra pair_context display field so the bulk-save
    # payload has multiple display rows interleaved with the two
    # seeded response rows.
    committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/display-fields",
        data={"source_pair": "pair_context:1", "label": "", "visible": "true"},
        follow_redirects=False,
    )
    body = committed_client.get(
        f"/operator/sessions/{session_id}/instruments?editing={instrument_id}"
    ).text
    import re

    # The page also carries a hidden ``<template>`` block holding
    # the JS "add a new response field" row markup; its
    # ``__TEMP_ID__`` / ``__DEFAULT_LABEL__`` placeholders match
    # the bulk-save form pattern, but the browser doesn't submit
    # them. Strip the templates before scraping to mirror that.
    body_no_templates = re.sub(
        r"<template[\s\S]*?</template>",
        "",
        body,
    )

    def _scrape(name: str) -> list[str]:
        # Bulk-save rows mix ``type="hidden"`` (display + the
        # response-row bookkeeping inputs) with ``type="text"``
        # (the visible response-label input). The regex matches
        # whichever, so the four parallel arrays stay in
        # rendered-form order regardless of input type. The
        # ``\s+`` between attributes survives the Jinja
        # template's line-wrapping of the visible input.
        pattern = (
            rf'<input\s+form="dfsave-{instrument_id}"\s+'
            rf'type="(?:hidden|text)"\s+name="{name}"\s+value="([^"]*)"'
        )
        return re.findall(pattern, body_no_templates)

    kinds = _scrape("kind")
    ids = _scrape("id")
    orders = _scrape("order")
    labels = _scrape("label")
    assert kinds, "bulk-save form should render at least one row"
    # All four parallel arrays line up — this is the contract
    # the route's misalignment check enforces.
    assert len(kinds) == len(ids) == len(orders) == len(labels)
    # Replay the live payload at the route: a 400 here means we
    # regressed back to the post-Slice-2 misalignment bug.
    response = committed_client.post(
        f"/operator/sessions/{session_id}/instruments/{instrument_id}/fields/save",
        data={
            "kind": kinds,
            "id": ids,
            "order": orders,
            "label": labels,
            "visible_ids": [
                rid for kind, rid in zip(kinds, ids) if kind == "display"
            ],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
