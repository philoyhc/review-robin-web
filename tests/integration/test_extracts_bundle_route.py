"""Integration tests for ``GET
/operator/sessions/{id}/export/bundle.zip`` — Segment 18D PR E1.

Covers the HTTP surface (content type, filename), the zip's five
members, and the ``session.bundle_extracted`` audit emission.
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
        data={"name": "Bundle", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_bundle_route_streams_zip_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bnd-fname")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="bnd-fname_bundle.zip"'
    )


def test_bundle_contains_the_five_csv_members(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bnd-five")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert sorted(archive.namelist()) == [
        "bnd-five_relationships.csv",
        "bnd-five_responses.csv",
        "bnd-five_reviewees.csv",
        "bnd-five_reviewers.csv",
        "bnd-five_settings.csv",
    ]
    # Each member is a non-empty, decodable CSV.
    for name in archive.namelist():
        assert archive.read(name).decode("utf-8").strip() != ""


def test_bundle_route_emits_audit_event_with_per_csv_counts(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bnd-aud")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail)["counts"]
    # A bare session: no rosters / responses, but Settings always
    # has rows.
    assert counts["reviewers"] == 0
    assert counts["reviewees"] == 0
    assert counts["relationships"] == 0
    assert counts["responses"] == 0
    assert counts["settings"] > 0
