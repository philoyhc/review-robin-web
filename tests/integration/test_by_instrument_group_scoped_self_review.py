"""Regression test for the latent ``SelfReview = FALSE`` hardcode
on group-scoped rows in the wide-format By-instrument extract,
fixed in PR 3 of ``guide/self_review_consolidate.md``.

Pre-PR-3: ``by_instrument_extract.py:436`` set ``self_review =
"FALSE"`` unconditionally on every group-scoped row, regardless of
whether the reviewer was a member of the group they were
reviewing (the whole-group rule from
``spec/assignments.md`` § *Self-review policy*).

Post-PR-3: the column carries the canonical value and the extract
reads it directly, so a reviewer reviewing their own group emits
``TRUE`` on every member-row of that group.

This test seeds Alice as both a reviewer and a member of her own
group, runs Generate, downloads the by-instrument CSV, and asserts
the SelfReview column reads ``TRUE`` on Alice's row about her
group.
"""
from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.services import assignments as assignments_service
from app.services.instruments import encode_group_kind


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "BIGroupSelf", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_group_scoped_self_review_row_reads_TRUE(
    client: TestClient, db: Session
) -> None:
    """Reviewer Alice reviews a tag_1=X group whose members
    include Alice herself + Bob. Pre-PR-3 the SelfReview column
    on the (single, collapsed) group row read ``FALSE``; post-
    PR-3 it reads ``TRUE`` because Alice is a member of her own
    group."""
    review_session = _make_session(client, db, code="bi-grp-self")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
        tag_1="X",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
        tag_1="X",
    )
    db.add_all([alice_r, alice_e, bob_e])
    db.flush()
    # Group-scoped instrument on reviewee.tag_1.
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.group_kind = encode_group_kind([("reviewee", "tag_1")])
    db.flush()
    # Materialise Alice's member-assignments for the group {Alice, Bob}.
    db.add_all(
        [
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=alice_e.id,
                instrument_id=instrument.id,
            ),
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=bob_e.id,
                instrument_id=instrument.id,
            ),
        ]
    )
    db.flush()
    # Mirror the production write path: recompute the column.
    assignments_service.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    payload = archive.read(archive.namelist()[0]).decode("utf-8")
    self_review_idx, data_rows = _self_review_column(payload)
    assert len(data_rows) >= 1
    for row in data_rows:
        cells = row.split(",")
        assert cells[self_review_idx] == "TRUE", (
            f"Expected SelfReview=TRUE on group-scoped row where "
            f"Alice is a member; got {cells[self_review_idx]!r}. "
            f"Row: {row}"
        )


def test_group_scoped_non_member_row_reads_FALSE(
    client: TestClient, db: Session
) -> None:
    """Control case: Alice reviews a group she's NOT a member of
    (tag_1=Y; Bob and Carol). SelfReview reads ``FALSE`` because
    Alice is not a member. Ensures we didn't over-correct."""
    review_session = _make_session(client, db, code="bi-grp-noself")
    alice_r = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email="alice@example.edu",
    )
    bob_e = Reviewee(
        session_id=review_session.id,
        name="Bob",
        email_or_identifier="bob@example.edu",
        tag_1="Y",
    )
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="Y",
    )
    db.add_all([alice_r, bob_e, carol_e])
    db.flush()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.group_kind = encode_group_kind([("reviewee", "tag_1")])
    db.flush()
    db.add_all(
        [
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=bob_e.id,
                instrument_id=instrument.id,
            ),
            Assignment(
                session_id=review_session.id,
                reviewer_id=alice_r.id,
                reviewee_id=carol_e.id,
                instrument_id=instrument.id,
            ),
        ]
    )
    db.flush()
    assignments_service.recompute_self_review_classification(
        db, session_id=review_session.id
    )
    db.commit()

    response = client.get(
        f"/operator/sessions/{review_session.id}"
        "/export/by_instrument_bundle.zip"
    )
    assert response.status_code == 200
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    payload = archive.read(archive.namelist()[0]).decode("utf-8")
    self_review_idx, data_rows = _self_review_column(payload)
    assert len(data_rows) >= 1
    for row in data_rows:
        cells = row.split(",")
        assert cells[self_review_idx] == "FALSE", (
            f"Expected SelfReview=FALSE on group Alice is not a "
            f"member of; got {cells[self_review_idx]!r}. Row: {row}"
        )


def _self_review_column(payload: str) -> tuple[int, list[str]]:
    """Locate the data-table header row in a By-instrument CSV
    (the line starting ``ReviewerName,``) and return its
    ``SelfReview`` column index plus the data rows following it."""
    lines = [line for line in payload.splitlines() if line.strip()]
    header_index = next(
        i for i, line in enumerate(lines) if line.startswith("ReviewerName,")
    )
    header = lines[header_index].split(",")
    return header.index("SelfReview"), lines[header_index + 1 :]
