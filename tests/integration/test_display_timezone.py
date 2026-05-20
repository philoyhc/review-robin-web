"""Segment 18B PR 2 / PR 3 — date / time rendering localises to the
resolved display timezone.

PR 2: operator surfaces render in the signed-in operator's
configured zone (``users.preferences['display_timezone']``).

PR 3: session-scoped surfaces render in the session's resolved
zone — ``sessions.display_timezone`` override → creating
operator's default → UTC.

Exercises the full filter-wiring chain: the auth / session
dependencies stamp ``request.state.display_timezone``; the
``date_filters`` context processor injects it; the context-aware
``format_datetime`` filter resolves the zone at render time.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession
from app.services.date_formatting import format_datetime
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _create_session(
    client: TestClient, db: Session, *, code: str = "tz-demo"
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _set_session_timezone(
    client: TestClient, session: ReviewSession, zone: str, **extra: str
):
    """Post the Edit Session Details form to set the display timezone.
    The standalone /timezone route was retired in 18B PR 5 — the
    timezone is now a field of the (lifecycle-gated) edit form, so
    this only works while the session is draft / validated."""
    data = {"name": session.name, "code": session.code,
            "display_timezone": zone}
    data.update(extra)
    return client.post(
        f"/operator/sessions/{session.id}/edit",
        data=data,
        follow_redirects=False,
    )


def test_lobby_renders_in_utc_before_any_preference(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)
    body = client.get("/operator/sessions").text
    assert format_datetime(session.created_at, "UTC") in body


def test_lobby_renders_in_operator_zone_after_save(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)

    client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Asia/Singapore"},
        follow_redirects=False,
    )

    body = client.get("/operator/sessions").text
    # The created-at pill now renders in Singapore time (+08)...
    assert format_datetime(session.created_at, "Asia/Singapore") in body
    # ...and the UTC render (a different wall-clock time) is gone.
    assert format_datetime(session.created_at, "UTC") not in body


def test_lobby_shows_session_timezone_column(
    client: TestClient, db: Session
) -> None:
    """The lobby names each row's resolved session zone in a Timezone
    column as a compact GMT-offset label, with the GMT-offset + raw
    IANA id in the title tooltip — the timestamp cells stay in the
    operator's zone since the table lists many sessions."""
    session = _create_session(client, db, code="tz-lobby")
    _set_session_timezone(client, session, "Asia/Singapore")

    body = client.get("/operator/sessions").text
    assert 'data-sort-key="timezone"' in body
    assert (
        '<abbr class="tz-gmt" title="GMT+8 Asia/Singapore">GMT+8</abbr>'
        in body
    )


# ── PR 3 — per-session timezone override ─────────────────────────────────


def test_new_session_stamped_with_operator_default(
    client: TestClient, db: Session
) -> None:
    """A new session captures the creating operator's default zone at
    create time (a snapshot, not a live link)."""
    client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Asia/Singapore"},
        follow_redirects=False,
    )
    session = _create_session(client, db, code="tz-stamp")
    assert session.display_timezone == "Asia/Singapore"


def test_new_session_stamped_utc_when_operator_has_no_default(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="tz-stamp-utc")
    assert session.display_timezone == "UTC"


def test_create_session_with_explicit_timezone_and_deadline(
    client: TestClient, db: Session
) -> None:
    """The Create form's timezone field sets the session zone, and the
    deadline picker is interpreted as wall-clock in that zone (18B PR 4)."""
    client.post(
        "/operator/sessions",
        data={
            "name": "TZ Create",
            "code": "tz-create",
            "display_timezone": "Asia/Singapore",
            "deadline": "2026-06-02T17:00",
        },
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tz-create")
    ).scalar_one()
    assert session.display_timezone == "Asia/Singapore"
    # 17:00 Singapore (+08) is stored as the 09:00 UTC instant.
    # Compared via format_datetime so the assertion is dialect-agnostic
    # (Postgres returns tz-aware, SQLite naive).
    assert format_datetime(session.deadline, "UTC") == "2026-06-02 09:00"


def test_create_page_renders_timezone_field(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/sessions/new").text
    assert 'name="display_timezone"' in body
    assert 'id="deadline-zone"' in body
    assert "Entered in" in body


def test_session_timezone_override_persists_and_audits(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="tz-ov")
    response = _set_session_timezone(client, session, "America/New_York")
    assert response.status_code == 303

    db.refresh(session)
    assert session.display_timezone == "America/New_York"

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.display_timezone_set"
        )
    ).scalar_one()
    # Stamped "UTC" at create (operator had no default), now New York.
    assert event.detail["changes"]["display_timezone"] == [
        "UTC",
        "America/New_York",
    ]
    assert event.session_id == session.id


def test_session_timezone_rejects_unknown_zone(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="tz-bad")
    response = _set_session_timezone(client, session, "Mars/Base")
    assert response.status_code == 422


def test_edit_deadline_interpreted_in_session_zone(
    client: TestClient, db: Session
) -> None:
    """The Edit form's deadline picker is wall-clock in the submitted
    timezone (18B PR 5)."""
    session = _create_session(client, db, code="tz-edit-dl")
    _set_session_timezone(
        client, session, "Asia/Singapore", deadline="2026-06-02T17:00"
    )
    db.refresh(session)
    assert session.display_timezone == "Asia/Singapore"
    # 17:00 Singapore (+08) is the 09:00 UTC instant.
    assert format_datetime(session.deadline, "UTC") == "2026-06-02 09:00"


def test_edit_page_renders_timezone_field(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="tz-card")
    body = client.get(f"/operator/sessions/{session.id}/edit").text
    # The timezone is a field of the Edit Session Details form now,
    # not a standalone card (18B PR 5).
    assert 'name="display_timezone"' in body
    assert '<option value="Asia/Singapore">' in body
    assert 'id="deadline-zone"' in body


def test_session_detail_renders_in_override_zone(
    client: TestClient, db: Session
) -> None:
    """A session-scoped page localises timestamps to the session's
    own override zone — not the viewing operator's default."""
    session = _create_session(client, db, code="tz-render")
    _set_session_timezone(client, session, "Asia/Singapore")
    db.refresh(session)

    body = client.get(f"/operator/sessions/{session.id}").text
    assert format_datetime(session.created_at, "Asia/Singapore") in body
    assert format_datetime(session.created_at, "UTC") not in body


def test_session_with_null_timezone_resolves_to_operator_default(
    client: TestClient, db: Session
) -> None:
    """A session whose display_timezone is NULL (legacy rows — the UI
    no longer produces NULL) resolves to the creating operator's
    current default."""
    session = _create_session(client, db, code="tz-inherit")
    client.post(
        "/operator/settings/timezone",
        data={"display_timezone": "Asia/Singapore"},
        follow_redirects=False,
    )
    session.display_timezone = None
    db.commit()

    body = client.get(f"/operator/sessions/{session.id}").text
    assert format_datetime(session.created_at, "Asia/Singapore") in body


def test_session_detail_shows_timezone_label(
    client: TestClient, db: Session
) -> None:
    """The Session Details card's Timezone item shows the resolved
    zone as a GMT-offset + raw IANA id."""
    session = _create_session(client, db, code="tz-label")
    _set_session_timezone(client, session, "Asia/Singapore")

    body = client.get(f"/operator/sessions/{session.id}").text
    assert "Timezone" in body
    assert "GMT+8 Asia/Singapore" in body


def _build_active_session_with_reviewer(
    operator: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    operator.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nR,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator.post(
        f"/operator/sessions/{session.id}/relationships/import",
        files={
            "file": (
                "rel.csv",
                (
                    f"ReviewerEmail,RevieweeEmail\n"
                    f"{reviewer_email},carol@example.edu\n"
                ).encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, session.id)
    generate_via_page_button(operator, session.id)
    operator.get(f"/operator/sessions/{session.id}/assignments?validated=1")
    operator.post(
        f"/operator/sessions/{session.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    db.refresh(session)
    return session


def test_reviewer_surface_renders_deadline_in_session_zone(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer surface localises the session deadline to the
    session's zone (18B PR 3 deadline-first verification)."""
    operator = make_client(alice)
    session = _build_active_session_with_reviewer(
        operator, db, code="tz-rev", reviewer_email="rae@example.edu"
    )
    # The session is Activated, so the (lifecycle-gated) edit form
    # can't set the zone — stamp it directly.
    session.deadline = datetime(2026, 6, 1, 2, 0)
    session.display_timezone = "Asia/Singapore"
    db.commit()
    db.refresh(session)

    reviewer = make_client(
        AuthenticatedUser(
            principal_id="rae-oid",
            email="rae@example.edu",
            name="Rae Reviewer",
            provider="aad",
        )
    )
    response = reviewer.get(f"/reviewer/sessions/{session.id}")
    assert response.status_code == 200
    # 02:00 UTC is 10:00 in Singapore — the deadline is converted to
    # the session zone (rendered bare, no zone token), with the
    # GMT-offset + raw IANA id in parentheses.
    assert format_datetime(session.deadline, "Asia/Singapore") in response.text
    assert format_datetime(session.deadline, "UTC") not in response.text
    assert "(GMT+8 Asia/Singapore)" in response.text


def test_reviewer_dashboard_shows_deadline_with_timezone_label(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """The reviewer dashboard renders each session's deadline in that
    session's zone, with the GMT-offset + raw IANA id in parentheses."""
    operator = make_client(alice)
    session = _build_active_session_with_reviewer(
        operator, db, code="tz-dash", reviewer_email="rae@example.edu"
    )
    # Activated session — stamp the zone directly (the edit form is
    # lifecycle-gated).
    session.deadline = datetime(2026, 6, 1, 2, 0)
    session.display_timezone = "Asia/Singapore"
    db.commit()
    db.refresh(session)

    reviewer = make_client(
        AuthenticatedUser(
            principal_id="rae-oid",
            email="rae@example.edu",
            name="Rae Reviewer",
            provider="aad",
        )
    )
    response = reviewer.get("/reviewer")
    assert response.status_code == 200
    # Post-17B-Phase-2 refinement: the deadline and Start columns
    # render zone-less; the Timezone column carries the GMT
    # offset, with the raw IANA id surfaced as a hover ``title``.
    assert format_datetime(session.deadline, "Asia/Singapore") in response.text
    assert 'title="GMT+8 Asia/Singapore"' in response.text
    assert ">GMT+8</abbr>" in response.text


# ── Timezone-sample preview on the config cards ──────────────────────────


def test_settings_card_renders_timezone_sample(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/settings").text
    assert 'id="tz-sample"' in body
    assert 'id="tz-sample-zone"' in body
    assert "Sample (right now):" in body
    # The SHOW_ZONE_TOKEN switch wires through to the preview JS.
    assert "var showToken = false;" in body
    # The preview resolves the zone's GMT-offset client-side.
    assert 'timeZoneName: "shortOffset"' in body


def test_edit_card_renders_timezone_sample(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, code="tz-sample")
    body = client.get(f"/operator/sessions/{session.id}/edit").text
    assert 'id="tz-sample"' in body
    assert 'id="tz-sample-zone"' in body
    assert "Sample (right now):" in body
    assert "var showToken = false;" in body
    assert 'timeZoneName: "shortOffset"' in body
