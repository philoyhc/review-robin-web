"""Integration tests for ``GET
/operator/sessions/{id}/export/responses.csv`` — Segment 12A-1
PR 4.

Per-row content shape is unit-tested in
``tests/unit/test_responses_extract.py``. These tests cover the
HTTP surface (auth, filename, audit emission), the empty-session
case, and the no-lifecycle-gate contract (works in draft +
ready).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Callable
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    InstrumentResponseField,
    Response,
    ReviewSession,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Responses", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_pair_with_response(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """Seed a session with a single reviewer/reviewee/assignment and
    one submitted Response so the route returns a non-empty body."""

    review_session = _make_session(client, db, code=code)
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nAlex,alex@example.edu\n",
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
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    db.expire_all()
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    field = InstrumentResponseField(
        instrument_id=instrument.id,
        field_key="overall",
        label="Overall",
        order=0,
        # iii-b4: FK retired; inline columns carry the data.
        _inline_data_type="integer",
        _inline_response_type="Likert5",
        _inline_list_csv="1,2,3,4,5",
    )
    db.add(field)
    db.flush()
    assignment = db.execute(
        select(Assignment).where(
            Assignment.session_id == review_session.id
        )
    ).scalar_one()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="4",
        )
    )
    db.flush()
    return review_session


def test_route_streams_csv_with_canonical_filename(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_with_response(
        client, db, code="rsp-fname"
    )
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == (
        'attachment; filename="rsp-fname_responses.csv"'
    )

    rows = list(csv.reader(io.StringIO(response.text)))
    # The file opens with a per-instrument preamble; locate the
    # data table by its header row.
    header_idx = next(
        i for i, r in enumerate(rows) if r and r[0] == "ReviewerName"
    )
    # 21 columns (PR 4a added ``SelfReview``; 13C D2 appended
    # ``InstrumentFlavour``).
    assert len(rows[header_idx]) == 21
    assert rows[header_idx][-1] == "InstrumentFlavour"
    # One body row from the seeded response.
    data = rows[header_idx + 1 :]
    assert len(data) == 1
    assert data[0][1] == "alex@example.edu"
    assert data[0][6] == "carol@example.edu"
    assert data[0][10] == "instrument_1"  # positional InstrumentName
    assert data[0][14] == "Likert5"
    assert data[0][15] == "4"
    assert data[0][16] == "FALSE"  # alex@ != carol@
    assert data[0][20] == "per-reviewee"  # InstrumentFlavour


def test_route_emits_audit_event_with_row_count(
    client: TestClient, db: Session
) -> None:
    review_session = _seed_pair_with_response(client, db, code="rsp-aud")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code == 200
    response.read()

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["session_code"] == "rsp-aud"
    assert detail["counts"]["rows"] == 1


def test_session_with_no_responses_emits_no_data_rows(
    client: TestClient, db: Session
) -> None:
    """A session with setup but no reviewer responses: the
    preamble still lists the instrument's fields, but there are no
    data rows below the header."""
    review_session = _make_session(client, db, code="rsp-empty")
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code == 200
    rows = list(csv.reader(io.StringIO(response.text)))
    header_idx = next(
        i for i, r in enumerate(rows) if r and r[0] == "ReviewerName"
    )
    # No data rows below the header.
    assert rows[header_idx + 1 :] == []
    # The preamble names the default instrument positionally.
    assert rows[0] == ["instrument_1"]

    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.responses_extracted",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    detail = cast(dict, event.detail)
    assert detail["counts"]["rows"] == 0


def test_route_works_in_every_lifecycle_state(
    client: TestClient, db: Session
) -> None:
    """No lifecycle gate — the responses extract is most useful
    in ``ready`` (mid-flight snapshot) and ``closed`` (final
    dataset). Spot-check that ``draft`` + ``ready`` both work."""

    review_session = _seed_pair_with_response(
        client, db, code="rsp-states"
    )
    # Draft state — hits before activation.
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code == 200

    # Activate.
    client.get(f"/operator/sessions/{review_session.id}/assignments?validated=1")
    activate = client.post(
        f"/operator/sessions/{review_session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert activate.status_code == 303

    # Activated state — extract still works.
    response = client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code == 200


def test_route_rejects_non_operator(
    db: Session,
    alice: AuthenticatedUser,
    bob: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    alice_client = make_client(alice)
    review_session = _make_session(alice_client, db, code="rsp-perm")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/export/responses.csv"
    )
    assert response.status_code in (403, 404)
