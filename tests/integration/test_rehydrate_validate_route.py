"""18P PR G3 — the wired Validate action on the rehydrate page.

Uploading an extract set to ``POST /operator/sessions/rehydrate/validate``
runs the analyzer, stashes a clean set, and re-renders the page with the
findings + preview; the Rehydrate button enables only on a clean verdict.
No session is created.
"""

from __future__ import annotations

import csv
import datetime as dt
import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    RehydrateStash,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.services.session_config_io import serialize_session_config
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers
from app.services.extracts.responses_extract import serialize_responses

_INLINE = dict(
    _inline_data_type="Integer",
    _inline_response_type="Likert5",
    _inline_min=1.0,
    _inline_max=5.0,
    _inline_step=1.0,
)


def _to_csv(rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _seed(db: Session) -> ReviewSession:
    user = User(email="src-op@e.edu", display_name="Src")
    db.add(user)
    db.flush()
    rs = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=user.id, role="owner"))
    inst = Instrument(
        session_id=rs.id, name="Inst", short_label="INST", order=1
    )
    db.add(inst)
    db.flush()
    field = InstrumentResponseField(
        instrument_id=inst.id,
        field_key="q1",
        label="Q1",
        order=1,
        visible=True,
        **_INLINE,
    )
    db.add(field)
    db.flush()
    rvr = Reviewer(session_id=rs.id, name="Ana", email="ana@e.edu")
    rve = Reviewee(session_id=rs.id, name="Bo", email_or_identifier="bo@e.edu")
    db.add_all([rvr, rve])
    db.flush()
    a = Assignment(
        session_id=rs.id,
        reviewer_id=rvr.id,
        reviewee_id=rve.id,
        instrument_id=inst.id,
        include=True,
        is_self_review=False,
    )
    db.add(a)
    db.flush()
    db.add(
        Response(
            assignment_id=a.id,
            response_field_id=field.id,
            value="4",
            saved_at=dt.datetime(2026, 6, 1, 9, 0, tzinfo=dt.timezone.utc),
            version=1,
        )
    )
    db.flush()
    return rs


def _file_set(db: Session, rs: ReviewSession) -> dict[str, bytes]:
    settings_rows = [("field", "value", "data_type")] + [
        (r.field, r.value, r.data_type)
        for r in serialize_session_config(db, rs)
    ]
    return {
        f"{rs.code}_settings.csv": _to_csv(settings_rows),
        f"{rs.code}_reviewers.csv": _to_csv(serialize_reviewers(db, rs)),
        f"{rs.code}_reviewees.csv": _to_csv(serialize_reviewees(db, rs)),
        f"{rs.code}_responses.csv": _to_csv(serialize_responses(db, rs)),
    }


def _multipart(files: dict[str, bytes]) -> list:
    return [("files", (name, content, "text/csv")) for name, content in files.items()]


def test_validate_clean_set_enables_rehydrate(
    client: TestClient, db: Session
) -> None:
    rs = _seed(db)
    response = client.post(
        "/operator/sessions/rehydrate/validate",
        files=_multipart(_file_set(db, rs)),
    )
    assert response.status_code == 200
    body = response.text
    assert "Validation passed" in body
    # The enabled Rehydrate button is a submit tied to the commit form.
    assert 'class="btn">Rehydrate</button>' in body
    # Preview.
    assert "Spring_REHYD" in body
    assert "1 reviewers" in body
    assert "1 response rows" in body
    # A stash row was created for the commit hand-off.
    assert db.execute(select(RehydrateStash)).scalars().first() is not None
    # No session was created.
    assert (
        db.execute(
            select(ReviewSession).where(ReviewSession.code == "spring-rehyd")
        ).scalar_one_or_none()
        is None
    )


def test_validate_incomplete_set_disables_rehydrate(
    client: TestClient, db: Session
) -> None:
    rs = _seed(db)
    files = _file_set(db, rs)
    del files[f"{rs.code}_responses.csv"]
    response = client.post(
        "/operator/sessions/rehydrate/validate",
        files=_multipart(files),
    )
    assert response.status_code == 200
    body = response.text
    assert "Fix the following" in body
    assert "responses.csv" in body
    # Rehydrate stays disabled; no clean set to stash.
    assert 'class="btn">Rehydrate</button>' not in body
    assert 'aria-disabled="true">Rehydrate</button>' in body
    assert db.execute(select(RehydrateStash)).scalars().first() is None
