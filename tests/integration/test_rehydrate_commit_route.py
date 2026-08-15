"""18P PR H — the wired Rehydrate (commit) action + orchestrator.

The commit route loads a validated set from the stash, re-runs the
analyzer, and on a clean verdict rebuilds a live ``_REHYD`` draft session
and redirects to its Session Home. These tests drive the full round-trip
through the HTTP surface: seed a source session, extract its files, POST
them to Validate to earn a token, then POST the token to Commit and assert
the reconstructed session matches.
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
    user = db.execute(
        select(User).where(User.email == "test@example.com")
    ).scalar_one_or_none()
    if user is None:
        user = User(email="test@example.com", display_name="Test")
        db.add(user)
        db.flush()
    rs = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=user.id, role="owner"))
    inst = Instrument(session_id=rs.id, name="Inst", short_label="INST", order=1)
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
            submitted_at=dt.datetime(2026, 6, 1, 9, 5, tzinfo=dt.timezone.utc),
            version=1,
        )
    )
    db.flush()
    return rs


def _file_set(db: Session, rs: ReviewSession) -> dict[str, bytes]:
    settings_rows = [("field", "value", "data_type")] + [
        (r.field, r.value, r.data_type) for r in serialize_session_config(db, rs)
    ]
    return {
        f"{rs.code}_settings.csv": _to_csv(settings_rows),
        f"{rs.code}_reviewers.csv": _to_csv(serialize_reviewers(db, rs)),
        f"{rs.code}_reviewees.csv": _to_csv(serialize_reviewees(db, rs)),
        f"{rs.code}_responses.csv": _to_csv(serialize_responses(db, rs)),
    }


def _multipart(files: dict[str, bytes]) -> list:
    return [
        ("files", (name, content, "text/csv")) for name, content in files.items()
    ]


def _validate_for_token(client: TestClient, files: dict[str, bytes]) -> str:
    response = client.post(
        "/operator/sessions/rehydrate/validate", files=_multipart(files)
    )
    assert response.status_code == 200, response.text
    assert "Validation passed" in response.text
    # The commit form carries the stash token in a hidden input.
    import re

    match = re.search(r'name="token" value="([^"]+)"', response.text)
    assert match, "no stash token rendered on a clean validate"
    return match.group(1)


def test_commit_rebuilds_session_from_extract(
    client: TestClient, db: Session
) -> None:
    rs = _seed(db)
    files = _file_set(db, rs)
    token = _validate_for_token(client, files)

    response = client.post(
        "/operator/sessions/rehydrate/commit",
        data={"token": token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/operator/sessions/" in location and "rehydrated=1" in location

    rehyd = db.execute(
        select(ReviewSession).where(ReviewSession.name == "Spring_REHYD")
    ).scalar_one()
    # Landed as a draft, never activated.
    assert rehyd.status == "draft"
    # Unique code, distinct from the source.
    assert rehyd.code == "spring-rehyd"
    assert rehyd.code != rs.code
    # Provenance note appended to the description.
    assert "Rehydrated" in (rehyd.description or "")
    assert "Not restored" in (rehyd.description or "")
    assert '"Spring"' in (rehyd.description or "")

    # Populations restored.
    reviewers = db.execute(
        select(Reviewer).where(Reviewer.session_id == rehyd.id)
    ).scalars().all()
    reviewees = db.execute(
        select(Reviewee).where(Reviewee.session_id == rehyd.id)
    ).scalars().all()
    assert {r.email for r in reviewers} == {"ana@e.edu"}
    assert {r.email_or_identifier for r in reviewees} == {"bo@e.edu"}

    # Instrument + response field restored.
    instruments = db.execute(
        select(Instrument).where(Instrument.session_id == rehyd.id)
    ).scalars().all()
    assert {i.short_label for i in instruments} == {"INST"}

    # The response value + timestamps + version round-tripped.
    new_responses = db.execute(
        select(Response)
        .join(Assignment, Response.assignment_id == Assignment.id)
        .where(Assignment.session_id == rehyd.id)
    ).scalars().all()
    assert len(new_responses) == 1
    r = new_responses[0]
    assert r.value == "4"
    assert r.version == 1
    assert r.saved_at.replace(tzinfo=None) == dt.datetime(2026, 6, 1, 9, 0)
    assert r.submitted_at.replace(tzinfo=None) == dt.datetime(2026, 6, 1, 9, 5)

    # The stash was consumed on a successful commit.
    assert db.execute(select(RehydrateStash)).scalars().first() is None


def test_commit_twice_derives_collision_name(
    client: TestClient, db: Session
) -> None:
    rs = _seed(db)
    files = _file_set(db, rs)

    token1 = _validate_for_token(client, files)
    r1 = client.post(
        "/operator/sessions/rehydrate/commit",
        data={"token": token1},
        follow_redirects=False,
    )
    assert r1.status_code == 303

    token2 = _validate_for_token(client, files)
    r2 = client.post(
        "/operator/sessions/rehydrate/commit",
        data={"token": token2},
        follow_redirects=False,
    )
    assert r2.status_code == 303

    names = set(
        db.execute(
            select(ReviewSession.name).where(
                ReviewSession.name.like("Spring_REHYD%")
            )
        ).scalars()
    )
    assert names == {"Spring_REHYD", "Spring_REHYD_1"}
    # Distinct unique codes.
    codes = set(
        db.execute(
            select(ReviewSession.code).where(
                ReviewSession.code.like("spring-rehyd%")
            )
        ).scalars()
    )
    assert len(codes) == 2


def test_commit_with_bad_token_creates_nothing(
    client: TestClient, db: Session
) -> None:
    _seed(db)
    before = db.execute(
        select(ReviewSession).where(ReviewSession.name.like("%_REHYD%"))
    ).scalars().all()
    assert before == []

    response = client.post(
        "/operator/sessions/rehydrate/commit",
        data={"token": "not-a-real-token"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "expired or is no longer available" in response.text
    # No session created.
    after = db.execute(
        select(ReviewSession).where(ReviewSession.name.like("%_REHYD%"))
    ).scalars().all()
    assert after == []
