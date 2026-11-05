"""Auto-send off until mail can go on a clock (segment 14E rung 0,
`RRW_SCHEDULED_SEND`). The suite runs with it on (`tests/conftest.py`);
these tests turn it off.

Off: the two offset fields render disabled with one line, a save keeps
the stored values unvalidated and ignores any posted, a create stores
none, no pass fires a scheduled invite or reminder (activation still
fires), and no caption, timeline row or Activate confirm promises an
automatic send. The Settings CSV still carries the stored values."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.web.views._workflow_card import (
    build_auto_send_invites_caption,
    build_auto_send_reminders_caption,
    build_manual_activate_cancellation,
    build_schedule_timeline,
)

from .test_scheduled_invites import (
    _generate_invitations,
    _operator,
    _seed_session_with_reviewers,
    _stub_build_url,
)

LINE = "Scheduled email is not available on this deployment."


@pytest.fixture
def send_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "scheduled_send", False)


def _local(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def _client_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    """A session the test client's operator owns."""
    response = client.post(
        "/operator/sessions",
        data={"name": f"Sess {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _events(db: Session, rs: ReviewSession, event_type: str) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == rs.id, AuditEvent.event_type == event_type
            )
        ).scalars()
    )


def test_the_shipped_default_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RRW_SCHEDULED_SEND", raising=False)
    assert Settings(_env_file=None).scheduled_send is False  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option
    monkeypatch.setenv("RRW_SCHEDULED_SEND", "true")
    assert Settings(_env_file=None).scheduled_send is True  # pyright: ignore[reportCallIssue]  -- a pydantic-settings init option


def test_the_fields_render_disabled_with_their_line(
    client: TestClient, db: Session, send_off: None
) -> None:
    page = client.get("/operator/sessions/new").text
    assert LINE in page
    assert (
        'name="invite_offsets"' in page
        and "disabled" in page.split('name="invite_offsets"')[1].split(">")[0]
    )

    rs = _client_session(client, db, "off-render")
    rs.invite_offsets = ["-P1D"]
    db.commit()
    home = client.get(f"/operator/sessions/{rs.public_id}?unlocked=1").text
    assert LINE in home
    for name in ("invite_offsets", "reminder_offsets"):
        tag = home.split(f'name="{name}"')[1].split(">")[0]
        assert "disabled" in tag, name
    assert 'value="-P1D"' in home  # the stored value is still shown


def test_session_home_shows_offsets_without_a_send_time(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _client_session(client, db, "off-display")
    rs.scheduled_activate_at = datetime.now(UTC) + timedelta(days=5)
    rs.invite_offsets = ["-P1D"]
    db.commit()
    home = client.get(f"/operator/sessions/{rs.public_id}").text
    assert 'class="config-value config-value-resolved"' not in home


def test_the_guide_says_auto_send_is_off(client: TestClient, send_off: None) -> None:
    assert LINE in client.get("/guide").text


def test_an_end_change_from_the_lobby_ignores_stored_reminders(db: Session, send_off: None) -> None:
    rs = _seed_session_with_reviewers(db, "off-lobby-end")
    # A stored reminder the new End would put inside the lead time.
    rs.reminder_offsets = ["-PT2H"]
    db.commit()
    scheduled_events.validate_deadline_change(
        db, rs, deadline=datetime.now(UTC) + timedelta(minutes=90)
    )


def test_on_the_fields_are_live(client: TestClient, db: Session) -> None:
    page = client.get("/operator/sessions/new").text
    assert LINE not in page
    assert "disabled" not in page.split('name="invite_offsets"')[1].split(">")[0]


def test_a_save_keeps_the_stored_offsets_and_ignores_posted_ones(
    client: TestClient, db: Session, send_off: None
) -> None:
    start = datetime.now(UTC) + timedelta(days=30)
    rs = _client_session(client, db, "off-save")
    rs.scheduled_activate_at = start
    # An entry that would now fail the lead-time rule: kept, not checked.
    rs.invite_offsets = ["-PT10M"]
    rs.reminder_offsets = ["-P1D"]
    db.commit()
    response = client.post(
        f"/operator/sessions/{rs.public_id}/config",
        data={
            "name": "Moved",
            "code": rs.code,
            "scheduled_activate_at": _local(start + timedelta(days=1)),
            "invite_offsets": "-P5D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(rs)
    assert rs.name == "Moved"
    assert rs.invite_offsets == ["-PT10M"]
    assert rs.reminder_offsets == ["-P1D"]


def test_a_create_stores_no_offsets(client: TestClient, db: Session, send_off: None) -> None:
    start = datetime.now(UTC) + timedelta(days=30)
    response = client.post(
        "/operator/sessions",
        data={
            "name": "Off create",
            "code": "off-create",
            "scheduled_activate_at": _local(start),
            "invite_offsets": "-P1D",
            "reminder_offsets": "-P1D",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(select(ReviewSession).where(ReviewSession.code == "off-create")).scalar_one()
    assert not rs.invite_offsets
    assert not rs.reminder_offsets


def test_no_pass_fires_invites_or_reminders_but_activation_runs(
    db: Session, send_off: None
) -> None:
    rs = _seed_session_with_reviewers(db, "off-fire", reviewer_count=2)
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.commit()
    _generate_invitations(db, rs, op)
    # Start just passed, with an invite entry due before it.
    rs.scheduled_activate_at = datetime.now(UTC) - timedelta(minutes=1)
    rs.invite_offsets = ["-P2D"]
    db.commit()

    scheduled_events.observe_scheduled_events(db, rs, build_invite_url=_stub_build_url)

    assert _events(db, rs, "session.scheduled_invites_fired") == []
    db.refresh(rs)
    assert rs.status == lifecycle.SessionStatus.ready.value
    assert rs.invite_offsets == ["-P2D"]  # kept for when sending is on


def test_no_reminder_fires(db: Session, send_off: None) -> None:
    rs = _seed_session_with_reviewers(db, "off-remind", reviewer_count=2)
    op = _operator(db, rs)
    rs.status = lifecycle.SessionStatus.validated.value
    db.commit()
    _generate_invitations(db, rs, op)
    rs.status = lifecycle.SessionStatus.ready.value
    rs.deadline = datetime.now(UTC) + timedelta(hours=1)
    rs.reminder_offsets = ["-P1D"]
    db.commit()

    scheduled_events.observe_scheduled_events(db, rs, build_invite_url=_stub_build_url)

    assert _events(db, rs, "session.scheduled_reminders_fired") == []


def test_nothing_promises_an_automatic_send(db: Session, send_off: None) -> None:
    rs = _seed_session_with_reviewers(db, "off-captions")
    rs.status = lifecycle.SessionStatus.validated.value
    rs.scheduled_activate_at = datetime.now(UTC) + timedelta(days=5)
    rs.deadline = datetime.now(UTC) + timedelta(days=10)
    rs.invite_offsets = ["-P1D"]
    rs.reminder_offsets = ["-P1D"]
    db.commit()

    assert build_auto_send_invites_caption(db, rs) is None
    assert build_auto_send_reminders_caption(db, rs) is None
    assert build_manual_activate_cancellation(rs) is None
    labels = [row["label"] for row in build_schedule_timeline(rs, "UTC")]
    assert labels == ["Session activates (Start)", "Session ends (End)"]


def test_the_settings_csv_still_carries_the_stored_offsets(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _client_session(client, db, "off-csv")
    rs.invite_offsets = ["-P1D"]
    rs.reminder_offsets = ["-P2D"]
    db.commit()
    text = client.get(f"/operator/sessions/{rs.public_id}/export/settings.csv").text
    assert "session.invite_offsets,-P1D" in text
    assert "session.reminder_offsets,-P2D" in text
