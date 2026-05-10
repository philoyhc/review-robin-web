"""Integration tests for ``GET
/operator/sessions/{id}/export/assignments.csv`` — Segment 12A-1
PR 3.

Per-row content shape is unit-tested in
``tests/unit/test_assignments_extract.py``. These tests cover the
HTTP surface (auth, manual-only 404 gate, audit emission), the
round-trip with the existing manual importer, and the card-render
behaviour (live row on manual, disabled row on rule-based /
full-matrix).
"""

from __future__ import annotations

import csv
import io
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.web import views
from ._full_matrix import full_matrix_seed_id


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Assignments", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_roster(client: TestClient, review_session: ReviewSession) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    "ReviewerName,ReviewerEmail\n"
                    "Alex,alex@example.edu\n"
                    "Bob,bob@example.edu\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    "RevieweeName,RevieweeEmail\n"
                    "Carol,carol@example.edu\n"
                    "Dan,dan@example.edu\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _upload_manual(client: TestClient, review_session: ReviewSession) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "a.csv",
                (
                    "ReviewerEmail,RevieweeEmail,IncludeAssignment\n"
                    "alex@example.edu,carol@example.edu,true\n"
                    "alex@example.edu,dan@example.edu,true\n"
                    "bob@example.edu,carol@example.edu,false\n"
                ).encode("utf-8"),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )


def _generate_full_matrix(
    client: TestClient, db: Session, review_session: ReviewSession
) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={"rule_set_id": full_matrix_seed_id(db), "exclude_self_review": ""},
        follow_redirects=False,
    )


# --------------------------------------------------------------------------- #
# Manual-mode happy path
# --------------------------------------------------------------------------- #


def test_manual_session_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-fname")
    _seed_roster(client, review_session)
    _upload_manual(client, review_session)
    db.refresh(review_session)
    assert review_session.assignment_mode == "manual"

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="m-fname_assignments.csv"'
    )

    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == [
        "ReviewerEmail",
        "RevieweeEmail",
        "IncludeAssignment",
        "Instrument",
    ]
    body = rows[1:]
    # Three uploaded rows — ordering is (reviewer, reviewee).
    assert [(r[0], r[1], r[2]) for r in body] == [
        ("alex@example.edu", "carol@example.edu", "true"),
        ("alex@example.edu", "dan@example.edu", "true"),
        ("bob@example.edu", "carol@example.edu", "false"),
    ]


def test_manual_session_round_trips_through_importer(
    client: TestClient, db: Session
) -> None:
    """Pull the CSV down, then upload the same bytes through the
    existing manual-import route on the same session — asserts the
    file feeds the importer without conversion."""

    review_session = _make_session(client, db, code="m-rt")
    _seed_roster(client, review_session)
    _upload_manual(client, review_session)

    extracted = client.get(
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert extracted.status_code == 200
    re_upload = client.post(
        f"/operator/sessions/{review_session.id}/assignments/manual/import",
        files={
            "file": (
                "round-trip.csv",
                extracted.text.encode("utf-8"),
                "text/csv",
            )
        },
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )
    # Importer accepts the round-trip without per-row issues — the
    # existing flow 303s on success.
    assert re_upload.status_code == 303


def test_manual_session_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="m-audit")
    _seed_roster(client, review_session)
    _upload_manual(client, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.assignments_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["session_code"] == "m-audit"
    assert detail["counts"]["rows"] == 3


# --------------------------------------------------------------------------- #
# Manual-only gate — non-manual sessions return 404
# --------------------------------------------------------------------------- #


def test_full_matrix_session_returns_404(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="fm-404")
    _seed_roster(client, review_session)
    _generate_full_matrix(client, db, review_session)
    db.refresh(review_session)
    assert review_session.assignment_mode == "rule_based"

    response = client.get(
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert response.status_code == 404


def test_unset_assignment_mode_returns_404(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="none-404")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert response.status_code == 404
    # No audit event should have fired on the rejection path.
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.assignments_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalars().all()
    assert events == []


# --------------------------------------------------------------------------- #
# Card render
# --------------------------------------------------------------------------- #


def test_card_assignments_row_live_on_manual_session(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="card-m")
    _seed_roster(client, review_session)
    _upload_manual(client, review_session)
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}
    assert by_key["assignments"].is_wired is True
    assert by_key["assignments"].download_url == (
        f"/operator/sessions/{review_session.id}/export/assignments.csv"
    )
    assert by_key["assignments"].coming_in is None
    assert by_key["assignments"].filename == "card-m_assignments.csv"


def test_card_assignments_row_disabled_with_note_on_rule_based(
    client: TestClient, db: Session
) -> None:
    """12C-1 PR 3 retired the standalone full-matrix route; the seeded
    Full Matrix RuleSet now writes ``assignment_mode='rule_based'``,
    so the extract card surfaces the rule-based "Manual export only"
    note here."""

    review_session = _make_session(client, db, code="card-rb")
    _seed_roster(client, review_session)
    _generate_full_matrix(client, db, review_session)
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}
    assert by_key["assignments"].is_wired is False
    assert by_key["assignments"].download_url is None
    assert by_key["assignments"].coming_in is not None
    assert "RuleSet" in by_key["assignments"].coming_in
    assert "Manual export only" in by_key["assignments"].coming_in


def test_card_assignments_row_disabled_with_note_on_unset_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="card-none")
    context = views.build_extract_data_context(db, review_session)
    by_key = {row.key: row for row in context.rows}
    assert by_key["assignments"].is_wired is False
    assert by_key["assignments"].download_url is None
    assert "No assignments generated yet" in by_key["assignments"].coming_in
