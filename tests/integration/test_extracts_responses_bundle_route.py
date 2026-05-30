"""Integration tests for ``GET
/operator/sessions/{id}/export/responses_bundle.zip`` — backs
the Extract data Operations tab's "Zip all" button per
``guide/extract_data.md``.

Covers the HTTP surface (content type, filename), the zip's
members, and the ``session.responses_bundle_extracted`` audit
emission. Also confirms the button is wired on the page.
"""

from __future__ import annotations

import io
import zipfile
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "RespBundle", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_responses_bundle_route_streams_zip_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-fname")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="rb-fname_responses.zip"'
    )


def test_responses_bundle_contains_only_response_csv_members(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-mem")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip"
    )
    assert response.status_code == 200

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    # Responses-only bundle: unified responses + reviewer/reviewee
    # stats + one per-instrument CSV. The auto-seeded default
    # instrument gives a bare session exactly one
    # ``instrument_1.csv``.
    assert sorted(archive.namelist()) == [
        "rb-mem_instrument_1.csv",
        "rb-mem_responses.csv",
        "rb-mem_reviewee_stats.csv",
        "rb-mem_reviewer_stats.csv",
    ]
    # Setup-side members are NOT in the responses bundle.
    names = set(archive.namelist())
    assert "rb-mem_reviewers.csv" not in names
    assert "rb-mem_reviewees.csv" not in names
    assert "rb-mem_relationships.csv" not in names
    assert "rb-mem_settings.csv" not in names


def test_responses_bundle_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-aud")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip"
    )
    assert response.status_code == 200

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail)["counts"]
    # A bare session — no responses; stats CSVs render with their
    # header only (count = 0 data rows).
    assert counts["responses"] == 0
    assert counts["reviewer_stats"] == 0
    assert counts["reviewee_stats"] == 0
    assert counts["instrument_files"] == 1


def test_extract_data_page_surfaces_zip_all_button(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rb-page")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'id="extract-data-zip-all"' in body
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/export/responses_bundle.zip"' in body
    )


def test_bundle_folds_in_saved_data_shapes(
    client: TestClient, db: Session
) -> None:
    """With the intro card's ``Data shaper`` chip default-on,
    every saved Data shape on the session contributes a
    ``{code}_{slug(name)}.csv`` member to the zip."""
    review_session = _make_session(client, db, code="rb-shapes")
    client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={
            "name": "My Shape",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name", "reviewer:email"],
        },
    )
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    # Slug strips the space.
    assert "rb-shapes_My_Shape.csv" in names


def test_data_shapes_zero_excludes_shapes(
    client: TestClient, db: Session
) -> None:
    """``?data_shapes=0`` drops the saved-shape members
    from the bundle (driven by the intro card's
    ``Data shaper`` chip when off)."""
    review_session = _make_session(client, db, code="rb-excl")
    client.post(
        f"/operator/sessions/{review_session.id}/extract-data/shapes",
        json={
            "name": "Hidden",
            "axis": "reviewer",
            "instrument_id": None,
            "response_field_id": None,
            "column_chip_slots": ["reviewer:name"],
        },
    )
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/responses_bundle.zip?data_shapes=0"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "rb-excl_Hidden.csv" not in names
