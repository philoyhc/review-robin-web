"""Integration tests for ``POST
/operator/sessions/{id}/import-config`` — Segment 12A-3 PR 3.

Covers route surface (auth, lifecycle gate, success / error
redirect shape, audit emission). The parse + apply contract is
unit-tested in ``tests/unit/test_apply_session_config.py``.
"""

from __future__ import annotations

import csv
import io
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    ReviewSession,
)


def _make_session(
    client: TestClient, db: Session, *, code: str = "ic-r"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Imp", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _build_csv(rows: list[tuple[str, str, str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def test_import_config_success_redirects_with_flash(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ic-ok")
    payload = _build_csv(
        [
            ("instruments[1].name", "Eval", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "config_imported=ok" in response.headers["location"]


def test_import_config_lifecycle_gate_rejects_ready(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ic-ready")
    review_session.status = "ready"
    db.commit()
    payload = _build_csv([("instruments[1].name", "X", "string")])
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=settings" in location
    assert "quick_setup_reason=lifecycle" in location


def test_import_config_parse_error_redirects_with_parse_reason(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ic-parse")
    # Missing required ``instruments[1].name`` ⇒ cross-row error.
    payload = _build_csv(
        [
            ("instruments[1].short_label", "X", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=settings" in location
    assert "quick_setup_reason=parse" in location


def test_import_config_bad_header_rejected(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ic-hdr")
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={
            "file": (
                "bad.csv",
                b"foo,bar,baz\n1,2,3\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_reason=parse" in response.headers["location"]


def test_import_config_emits_audit_event(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ic-audit")
    payload = _build_csv(
        [
            ("instruments[1].name", "Eval", "string"),
        ]
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.settings_imported",
            AuditEvent.session_id == review_session.id,
        )
    ).scalar_one()
    counts = cast(dict, event.detail).get("counts", {})
    assert counts.get("instruments") == 1


def test_import_config_route_rejects_non_operator(
    db: Session,
    alice: object,
    bob: object,
    make_client: object,
) -> None:
    alice_client = make_client(alice)  # type: ignore[operator]
    review_session = _make_session(alice_client, db, code="ic-perm")

    bob_client = make_client(bob)  # type: ignore[operator]
    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/import-config",
        data={"confirm_replace": "true"},
        files={"file": ("c.csv", b"field,value,data_type\n", "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code in (403, 404)


def _session_with_a_response(client: TestClient, db: Session, code: str):
    from app.db.models import (
        Assignment,
        Instrument,
        InstrumentResponseField,
        Response,
        Reviewee,
        Reviewer,
    )

    review_session = _make_session(client, db, code=code)
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalars().first()
    field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).scalars().first()
    reviewer = Reviewer(
        session_id=review_session.id, name="Ana", email="ana@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ben",
        email_or_identifier="ben@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
        include=True,
        created_by_mode="rule_based",
    )
    db.add(assignment)
    db.flush()
    db.add(
        Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value="5",
        )
    )
    db.commit()
    return review_session


def test_a_settings_replace_needs_the_tick_and_the_response_loss_ack(
    client: TestClient, db: Session
) -> None:
    """A settings CSV rebuilds every instrument, deleting assignments and
    responses. The server refuses it without the replacement tick, and,
    where responses exist, without the response-loss acknowledgement;
    nothing is deleted on a refusal (findings C3)."""
    from app.db.models import Response

    review_session = _session_with_a_response(client, db, "ic-c3")
    payload = _build_csv([("instruments[1].name", "Eval", "string")])
    url = f"/operator/sessions/{review_session.id}/import-config"

    for data in ({}, {"confirm_replace": "true"}):
        response = client.post(
            url,
            data=data,
            files={"file": ("config.csv", payload, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "quick_setup_reason=needs_confirm" in response.headers["location"]
        db.expire_all()
        assert db.execute(select(Response)).scalars().all() != []

    response = client.post(
        url,
        data={"confirm_replace": "true", "acknowledge_response_loss": "true"},
        files={"file": ("config.csv", payload, "text/csv")},
        follow_redirects=False,
    )
    assert "config_imported=ok" in response.headers["location"]
    db.expire_all()
    assert db.execute(select(Response)).scalars().all() == []
