"""14F rung 3d: the participation report.

- Every arrival on the review surface or the summary stamps
  ``Reviewer.last_opened_at``, whichever link brought the reviewer, and
  leaves ``updated_at`` alone (it reads as a roster edit on Setup).
- Reviewer response metadata's **Timestamps** chip, off by default, adds
  ``LastOpened`` / ``LastSaved`` / ``LastSubmitted``, also through the
  Zip all bundle.
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime

from _rrw_app import rrw_app
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    Reviewer,
    ReviewSession,
)
from app.services import reviewers as reviewers_service

from .test_invitations import _ready_session

app = rrw_app()

RAE = AuthenticatedUser(
    principal_id="rae-oid", email="rae@example.edu", name="Rae Reviewer", provider="aad"
)


def _rae(db: Session, session: ReviewSession) -> Reviewer:
    return db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id, Reviewer.email == RAE.email)
    ).scalar_one()


def _metadata(client: TestClient, session: ReviewSession, query: str = "") -> list[list[str]]:
    response = client.get(
        f"/operator/sessions/{session.public_id}/export/reviewer_metadata.csv{query}"
    )
    assert response.status_code == 200
    return list(csv.reader(io.StringIO(response.text)))


def test_a_visit_stamps_last_opened_and_leaves_updated_at(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="ts-visit")
    reviewer = _rae(db, session)
    updated_before = reviewer.updated_at
    assert reviewer.last_opened_at is None
    operator = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = lambda: RAE
    try:
        assert client.get(f"/me/sessions/{session.public_id}/1").status_code == 200
    finally:
        app.dependency_overrides[get_current_user] = operator
    db.refresh(reviewer)
    assert reviewer.last_opened_at is not None
    assert reviewer.updated_at == updated_before


def test_off_by_default_the_header_is_unchanged(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="ts-off")
    header = _metadata(client, session)[0]
    assert "LastOpened" not in header
    page = client.get(f"/operator/sessions/{session.public_id}/extract-data").text
    chip = page.split('data-reviewer-metadata-chip="timestamps"', 1)[1].split(">", 1)[0]
    assert 'aria-pressed="false"' in chip


def test_on_the_three_columns_follow_name_and_email(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="ts-on")
    reviewer = _rae(db, session)
    reviewers_service.mark_opened(db, reviewer, now=datetime(2026, 11, 3, 1, 0, tzinfo=UTC))
    assignment = (
        db.execute(select(Assignment).where(Assignment.reviewer_id == reviewer.id))
        .scalars()
        .first()
    )
    assert assignment is not None
    field = (
        db.execute(
            select(InstrumentResponseField).where(
                InstrumentResponseField.instrument_id == assignment.instrument_id
            )
        )
        .scalars()
        .first()
    )
    assert field is not None
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="ok",
            saved_at=datetime(2026, 11, 4, 2, 0, tzinfo=UTC),
            submitted_at=datetime(2026, 11, 4, 3, 0, tzinfo=UTC),
        )
    )
    db.commit()
    rows = _metadata(client, session, "?timestamps=1")
    assert rows[0][:5] == [
        "ReviewerName",
        "ReviewerEmail",
        "LastOpened",
        "LastSaved",
        "LastSubmitted",
    ]
    [rae_row] = [row for row in rows[1:] if row[1] == RAE.email]
    opened, saved, submitted = rae_row[2:5]
    assert opened.startswith("2026-11-03")
    assert saved.startswith("2026-11-04")
    assert submitted.startswith("2026-11-04")
    assert saved < submitted


def test_a_reviewer_who_never_came_reads_empty(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="ts-never")
    rows = _metadata(client, session, "?timestamps=1")
    [rae_row] = [row for row in rows[1:] if row[1] == RAE.email]
    assert rae_row[2:5] == ["", "", ""]


def test_zip_all_carries_the_chip(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="ts-zip")
    response = client.get(
        f"/operator/sessions/{session.public_id}/export/responses_bundle.zip"
        "?reviewer_metadata.timestamps=1"
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        [name] = [n for n in bundle.namelist() if "reviewer_metadata" in n]
        reviewer_header = bundle.read(name).decode().split("\r\n", 1)[0]
        [name] = [n for n in bundle.namelist() if "reviewee_metadata" in n]
        reviewee_header = bundle.read(name).decode().split("\r\n", 1)[0]
    assert "LastOpened,LastSaved,LastSubmitted" in reviewer_header
    assert "LastOpened" not in reviewee_header
