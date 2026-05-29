"""Integration tests for ``GET
/operator/sessions/{id}/export/by_instrument_bundle.zip`` —
backs the Extract data tab's By-instrument Zip-all button per
``guide/extract_data.md``.

Covers HTTP surface (content type, filename), member naming
+ contents (meta block + data block), and the
``session.by_instrument_bundle_extracted`` audit emission.
"""

from __future__ import annotations

import io
import zipfile
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "ByInst", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _default_instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


def test_route_streams_zip_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-fname")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"] == (
        'attachment; filename="bi-fname_by_instrument.zip"'
    )


def test_members_named_by_instrument_short_label(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-slug")
    instrument = _default_instrument(db, review_session.id)
    instrument.short_label = "Peer Review"
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    assert response.status_code == 200

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = archive.namelist()
    # Space sanitised to underscore.
    assert names == ["bi-slug_by_instrument_Peer_Review.csv"]


def test_members_fall_back_to_positional_label_when_short_label_blank(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-fb")
    instrument = _default_instrument(db, review_session.id)
    instrument.short_label = None
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert archive.namelist() == [
        "bi-fb_by_instrument_Instrument_1.csv",
    ]


def test_meta_block_carries_instrument_identity_and_self_review_flag(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-meta")
    instrument = _default_instrument(db, review_session.id)
    instrument.short_label = "PR"
    instrument.description = "Peer review instrument"
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    payload = archive.read(archive.namelist()[0]).decode("utf-8")

    assert "Instrument,PR" in payload
    assert "Description,Peer review instrument" in payload
    # Pool / unit-of-review / self-review meta rows present.
    assert "Pool of reviewers," in payload
    assert "Pool of reviewees," in payload
    assert "Unit of review,Individual" in payload
    assert "Self-review excluded,No" in payload
    # Assignment count line present.
    assert "Number of assignments," in payload


def test_meta_block_emits_response_field_4_row_subblock(
    client: TestClient, db: Session
) -> None:
    """The default seeded instrument carries a single response
    field — its meta sub-block surfaces the 4 documented rows
    (Response field / Data Type / Min,Max,Step,List / Helptext)."""
    review_session = _make_session(client, db, code="bi-field-meta")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    payload = archive.read(archive.namelist()[0]).decode("utf-8")

    assert "Response field," in payload
    assert "Data Type," in payload
    assert '"Min, Max, Step, List",' in payload
    assert "Helptext," in payload


def test_data_block_carries_wide_header_with_field_labels(
    client: TestClient, db: Session
) -> None:
    """The data table's header column list includes the
    per-field labels between the reviewer/reviewee identity
    blocks and the SelfReview/SavedAt/SubmittedAt tail."""
    review_session = _make_session(client, db, code="bi-hdr")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    payload = archive.read(archive.namelist()[0]).decode("utf-8")

    # Tail columns present in order.
    assert "SelfReview,SavedAt,SubmittedAt" in payload
    # Reviewer + reviewee identity blocks present.
    assert "ReviewerName,ReviewerEmail," in payload
    assert "RevieweeName,RevieweeEmail," in payload


def test_route_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-aud")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    assert response.status_code == 200

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type
            == "session.by_instrument_bundle_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail)["counts"]
    # Default-seeded session has one instrument.
    assert counts["instrument_files"] == 1


def test_extract_data_page_links_button_to_by_instrument_bundle(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="bi-page")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'id="extract-data-by-instrument-zip"' in body
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/export/by_instrument_bundle.zip"' in body
    )
    # "Zip all responses" button still wired (intro card).
    assert "Zip all responses" in body
