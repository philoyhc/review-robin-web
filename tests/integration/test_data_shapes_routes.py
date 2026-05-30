"""Integration tests for the Data shapes CRUD HTTP surface +
the page-render of saved shapes (PR 3 of the Data shaper
wiring slice).

Covers:

* ``POST /sessions/{id}/extract-data/shapes`` — happy path
  + 422 on validation failure + 422 on UNIQUE conflict.
* ``PATCH .../{shape_id}`` — happy path + 404 on cross-
  session shape_id + 422 on validation drift.
* ``DELETE .../{shape_id}`` — happy path + idempotent
  re-delete returns 204.
* ``GET /sessions/{id}/extract-data`` — saved shapes
  render server-side as ``data-shape-mode="saved"``
  sub-cards carrying the persistence attributes the JS
  reads on ``Edit``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataShape, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "DS", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _payload(
    *,
    name: str = "My shape",
    axis: str = "reviewer",
    instrument_id: int | None = None,
    response_field_id: int | None = None,
    column_chip_slots: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "axis": axis,
        "instrument_id": instrument_id,
        "response_field_id": response_field_id,
        "column_chip_slots": column_chip_slots
        or ["reviewer:name", "reviewer:email"],
    }


# --------------------------------------------------------------------------- #
# POST
# --------------------------------------------------------------------------- #


def test_post_creates_shape_and_returns_201(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="post-ok")
    response = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(name="Created"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Created"
    assert body["axis"] == "reviewer"
    assert body["column_chip_slots"] == [
        "reviewer:name",
        "reviewer:email",
    ]
    # Row persisted.
    db.expire_all()
    rows = db.execute(
        select(DataShape).where(
            DataShape.session_id == review_session.id
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].name == "Created"


def test_post_invalid_axis_returns_422(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="post-axis")
    response = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(axis="instrument"),
    )
    assert response.status_code == 422
    body = response.json()
    assert "Axis" in body["error"]
    assert body["conflict"] is False


def test_post_duplicate_name_returns_422_with_conflict_flag(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="post-conflict")
    client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(name="dupe"),
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(name="dupe"),
    )
    assert response.status_code == 422
    body = response.json()
    assert body["conflict"] is True


# --------------------------------------------------------------------------- #
# PATCH
# --------------------------------------------------------------------------- #


def test_patch_updates_shape(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="patch-ok")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(name="initial"),
    ).json()
    response = client.patch(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}",
        json=_payload(
            name="renamed",
            axis="reviewee",
            column_chip_slots=["reviewee:name", "reviewee:email"],
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "renamed"
    assert body["axis"] == "reviewee"
    db.expire_all()
    row = db.execute(
        select(DataShape).where(DataShape.id == created["id"])
    ).scalar_one()
    assert row.name == "renamed"
    assert row.axis == "reviewee"


def test_patch_cross_session_shape_returns_404(
    client: TestClient, db: Session
) -> None:
    """A shape_id from a different session must not be
    PATCHable from the current session."""
    session_a = _make_session(client, db, code="patch-a")
    session_b = _make_session(client, db, code="patch-b")
    created = client.post(
        f"/operator/sessions/{session_a.id}/extract-data/shapes",
        json=_payload(),
    ).json()
    response = client.patch(
        f"/operator/sessions/{session_b.id}"
        f"/extract-data/shapes/{created['id']}",
        json=_payload(name="hijack"),
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# DELETE
# --------------------------------------------------------------------------- #


def test_delete_removes_shape(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="del-ok")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(),
    ).json()
    response = client.delete(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}"
    )
    assert response.status_code == 204
    db.expire_all()
    assert (
        db.execute(
            select(DataShape).where(DataShape.id == created["id"])
        ).scalar_one_or_none()
        is None
    )


def test_delete_is_idempotent(client: TestClient, db: Session) -> None:
    review_session = _make_session(client, db, code="del-idem")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(),
    ).json()
    first = client.delete(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}"
    )
    second = client.delete(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}"
    )
    assert first.status_code == 204
    assert second.status_code == 204


# --------------------------------------------------------------------------- #
# Page render
# --------------------------------------------------------------------------- #


def test_page_renders_saved_shapes_with_persistence_attrs(
    client: TestClient, db: Session
) -> None:
    """Saved shapes render as ``data-shape-mode="saved"``
    sub-cards before the (no-longer-present-when-shapes-
    exist) initial blank. Each carries the persistence
    attributes the JS reads on ``Edit`` to restore chip
    state + identify the row for PATCH / DELETE."""
    review_session = _make_session(client, db, code="render")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(
            name="Visible",
            column_chip_slots=[
                "reviewer:name",
                "reviewer:email",
                "reviewer:assigned",
            ],
        ),
    ).json()
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    # Each saved shape's sub-card carries its id + axis +
    # column-slots JSON on a ``data-shape-mode="saved"`` div.
    assert f'data-shape-id="{created["id"]}"' in body
    assert 'data-shape-mode="saved"' in body
    assert 'data-shape-axis="reviewer"' in body
    # ``data-shape-column-slots`` carries the JSON-encoded
    # slot list. Rendered into a **single-quoted** attribute
    # so the JSON's double quotes don't conflict — Jinja's
    # ``tojson`` filter returns a Markup string that
    # subsequent ``| e`` no-ops on, so the previous
    # double-quoted form collapsed to an empty attribute.
    expected_slots_attr = (
        'data-shape-column-slots=\'["reviewer:name", '
        '"reviewer:email", "reviewer:assigned"]\''
    )
    assert expected_slots_attr in body
    # Preview row pre-populated with the **canonical CSV
    # headers** (``ReviewerName`` etc.) — same labels the
    # download row carries — not the raw chip slot
    # strings. Aggregate columns carry the Self-review
    # handling chip's ``_self`` / ``_noself`` suffix per
    # ``guide/extract_data.md`` § *Self-review handling*
    # (PR B); ``include_self`` is the default state on a
    # freshly-saved shape.
    assert ">ReviewerName<" in body
    assert ">ReviewerEmail<" in body
    assert ">Assigned_self<" in body
    # ``data-shape-column-headers`` carries the JSON-encoded
    # canonical header list — used by the post-Cancel /
    # close-other-editing ``renderSavedPreviewRow`` path.
    assert (
        "data-shape-column-headers='[\"ReviewerName\", "
        "\"ReviewerEmail\", \"Assigned_self\"]'"
    ) in body
    # The always-present blank initial card does NOT render
    # when shapes exist — operator uses ``+Shape`` to spawn
    # a new editable card if they want one.
    stack_block = body.split("data-shaper-stack")[1].split(
        'id="extract-data-shaper-zip"'
    )[0]
    assert stack_block.count('data-shape-mode="edit"') == 0


def test_page_renders_initial_blank_when_no_shapes_exist(
    client: TestClient, db: Session
) -> None:
    """No saved shapes → always-present blank edit-mode
    sub-card renders so the operator has an immediate edit
    target (band-3 builder pattern)."""
    review_session = _make_session(client, db, code="no-shapes")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    stack_block = body.split("data-shaper-stack")[1].split(
        'id="extract-data-shaper-zip"'
    )[0]
    assert 'data-shape-mode="edit"' in stack_block


# --------------------------------------------------------------------------- #
# GET download.csv
# --------------------------------------------------------------------------- #


def test_download_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="dl-name")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(
            name="My Shape!",
            column_chip_slots=["reviewer:name", "reviewer:email"],
        ),
    ).json()
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}/download.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    # Slug strips the non-alphanumeric ``!`` and the space.
    # Default Self-review handling state (``include_self``) maps
    # to the ``_self`` filename suffix per PR B of the chip slice
    # in ``guide/extract_data.md`` § *Self-review handling*.
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="dl-name_My_Shape_self.csv"'
    )


def test_download_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    from app.db.models import AuditEvent

    review_session = _make_session(client, db, code="dl-aud")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(),
    ).json()
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}/download.csv"
    )
    assert response.status_code == 200
    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["refs"]["shape_id"] == created["id"]
    # Fresh session, no reviewers → 0 body rows.
    assert detail["counts"]["rows"] == 0


def test_download_cross_session_shape_returns_404(
    client: TestClient, db: Session
) -> None:
    session_a = _make_session(client, db, code="dl-a")
    session_b = _make_session(client, db, code="dl-b")
    created = client.post(
        f"/operator/sessions/{session_a.id}/extract-data/shapes",
        json=_payload(),
    ).json()
    response = client.get(
        f"/operator/sessions/{session_b.id}"
        f"/extract-data/shapes/{created['id']}/download.csv"
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# Self-review handling chip — PR B
# --------------------------------------------------------------------------- #


def test_post_round_trips_self_review_handling_state(
    client: TestClient, db: Session
) -> None:
    """Posting a payload with ``self_review_handling=exclude_self``
    persists the value on the row + echoes it back on the
    response."""
    review_session = _make_session(client, db, code="srh-post")
    response = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={**_payload(), "self_review_handling": "exclude_self"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["self_review_handling"] == "exclude_self"
    db.expire_all()
    row = db.execute(
        select(DataShape).where(DataShape.id == body["id"])
    ).scalar_one()
    assert row.self_review_handling == "exclude_self"


def test_patch_can_flip_self_review_handling(
    client: TestClient, db: Session
) -> None:
    """PATCH updates the persisted state."""
    review_session = _make_session(client, db, code="srh-patch")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json=_payload(name="To flip"),
    ).json()
    assert created["self_review_handling"] == "include_self"
    response = client.patch(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}",
        json={**_payload(name="To flip"), "self_review_handling": "both"},
    )
    assert response.status_code == 200
    assert response.json()["self_review_handling"] == "both"


def test_post_rejects_unknown_self_review_handling(
    client: TestClient, db: Session
) -> None:
    """A bogus state string returns 422 from the service-layer
    validator."""
    review_session = _make_session(client, db, code="srh-bogus")
    response = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={**_payload(), "self_review_handling": "garbage"},
    )
    assert response.status_code == 422


def test_download_filename_carries_state_suffix(
    client: TestClient, db: Session
) -> None:
    """The Self-review handling chip's filename suffix
    (``_self`` / ``_noself`` / ``_both``) lands between the
    shape's name-slug and the ``.csv`` extension."""
    review_session = _make_session(client, db, code="dl-srh")
    for state, expected_suffix in (
        ("include_self", "_self"),
        ("exclude_self", "_noself"),
        ("both", "_both"),
    ):
        created = client.post(
            f"/operator/sessions/{review_session.id}/extract-data/shapes",
            json={
                **_payload(name=f"Shape-{state}"),
                "self_review_handling": state,
            },
        ).json()
        response = client.get(
            f"/operator/sessions/{review_session.id}"
            f"/extract-data/shapes/{created['id']}/download.csv"
        )
        assert response.status_code == 200
        assert (
            response.headers["content-disposition"]
            == (
                f'attachment; filename="dl-srh_Shape-{state}{expected_suffix}.csv"'
            )
        )


def test_download_audit_event_carries_context_self_review_handling(
    client: TestClient, db: Session
) -> None:
    """The ``session.data_shape_extracted`` audit event picks up
    the chip state on the ``context`` slot."""
    from app.db.models import AuditEvent

    review_session = _make_session(client, db, code="srh-aud")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={**_payload(), "self_review_handling": "both"},
    ).json()
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/extract-data/shapes/{created['id']}/download.csv"
    )
    assert response.status_code == 200
    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.data_shape_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = event.detail
    assert detail["context"]["self_review_handling"] == "both"


def test_saved_shape_renders_self_review_handling_attr_on_card(
    client: TestClient, db: Session
) -> None:
    """PR C — the saved sub-card carries its persisted chip
    state as ``data-shape-self-review-handling`` so the JS can
    sync the scope-row chip on Edit and so the dirty-state Save
    gate has something to compare against."""
    review_session = _make_session(client, db, code="srh-render")
    created = client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={**_payload(name="Excludey"), "self_review_handling": "exclude_self"},
    ).json()
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text
    assert f'data-shape-id="{created["id"]}"' in body
    assert 'data-shape-self-review-handling="exclude_self"' in body
