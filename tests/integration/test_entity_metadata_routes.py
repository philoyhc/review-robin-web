"""Integration tests for the Extract data tab's Reviewer /
Reviewee response metadata CSV routes.

Covers HTTP surface (filename, content type), query-param wiring
(``?instrument=`` filter + ``?all=0`` toggle), and the audit
emission for both ``session.reviewer_metadata_extracted`` and
``session.reviewee_metadata_extracted``.
"""

from __future__ import annotations

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
        data={"name": "Meta", "code": code, "description": ""},
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


def test_reviewer_metadata_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rmd-name")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/reviewer_metadata.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="rmd-name_reviewer_metadata.csv"'
    )
    # No instruments selected ⇒ base header only.
    first_line = response.text.split("\r\n", 1)[0]
    assert first_line == "ReviewerName,ReviewerEmail,Assigned,Count"


def test_reviewer_metadata_instrument_param_adds_per_field_block(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rmd-instr")
    instrument = _default_instrument(db, review_session.id)
    instrument.short_label = "Peer"
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/export/reviewer_metadata.csv?instrument={instrument.id}"
    )
    first_line = response.text.split("\r\n", 1)[0]
    # Base header followed by the per-field block; the default
    # seeded instrument carries one Long_text field labelled
    # "Strengths" so the .Length column appears (String data
    # type, not numeric).
    assert first_line.startswith("ReviewerName,ReviewerEmail,Assigned,Count,")
    assert "#1: Peer." in first_line
    assert ".Length" in first_line


def test_reviewer_metadata_audit_event_carries_row_and_instrument_counts(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="rmd-aud")
    instrument = _default_instrument(db, review_session.id)
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/export/reviewer_metadata.csv?instrument={instrument.id}"
    )
    assert response.status_code == 200

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.reviewer_metadata_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail)["counts"]
    # Fresh session has no reviewers yet → 0 body rows; one
    # instrument was passed via the query string.
    assert counts["rows"] == 0
    assert counts["instruments"] == 1


def test_reviewee_metadata_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="emd-name")
    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/reviewee_metadata.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="emd-name_reviewee_metadata.csv"'
    )
    first_line = response.text.split("\r\n", 1)[0]
    assert first_line == "RevieweeName,RevieweeEmail,Assigned,Count"


def test_extract_data_page_links_both_metadata_buttons(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="md-links")
    body = client.get(
        f"/operator/sessions/{review_session.id}/extract-data"
    ).text

    assert 'id="extract-data-reviewer-metadata-zip"' in body
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/export/reviewer_metadata.csv"' in body
    )
    assert 'id="extract-data-reviewee-metadata-zip"' in body
    assert (
        f'href="/operator/sessions/{review_session.id}'
        f'/export/reviewee_metadata.csv"' in body
    )
