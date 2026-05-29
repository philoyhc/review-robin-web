"""Integration tests for ``GET
/operator/sessions/{id}/export/bundle.zip`` — the setup-only
zip backing the Session Home Extract Setup card. Renamed from
"session bundle" on 2026-05-29 when responses-data downloads
moved off to the Extract data Operations tab (per
``guide/extract_data.md``).

Covers the HTTP surface (content type, filename), the zip's
members, and the ``session.setup_bundle_extracted`` audit
emission.
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
    # Filename changed from ``{code}_bundle.zip`` to
    # ``{code}_setup.zip`` on 2026-05-29 when the bundle slimmed
    # to setup-only.
    assert response.headers["content-disposition"] == (
        'attachment; filename="bnd-fname_setup.zip"'
    )


def test_bundle_contains_only_the_setup_csv_members(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bnd-mem")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/bundle.zip"
    )
    assert response.status_code == 200

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    # Setup-only bundle: Reviewers / Reviewees / Relationships /
    # Settings. Responses + reviewer/reviewee stats +
    # per-instrument files moved to the responses bundle (per
    # ``guide/extract_data.md``).
    assert sorted(archive.namelist()) == [
        "bnd-mem_relationships.csv",
        "bnd-mem_reviewees.csv",
        "bnd-mem_reviewers.csv",
        "bnd-mem_settings.csv",
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
            AuditEvent.event_type == "session.setup_bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail)["counts"]
    # Setup-only bundle counts.
    assert counts["reviewers"] == 0
    assert counts["reviewees"] == 0
    assert counts["relationships"] == 0
    assert counts["settings"] > 0
    # Response-side counts no longer present.
    assert "responses" not in counts
    assert "reviewer_stats" not in counts
    assert "reviewee_stats" not in counts
    assert "instrument_files" not in counts
