"""A Quick Setup upload that gives Observers or Relationships rows turns
that tab on.

``guide/quick_setup_update.md`` Item 2 (author, 2026-10-12): the
converse of the lock-on-data invariant (``spec/participant_model.md``),
so rows never sit behind a hidden tab. Set inside the all-or-nothing
unit, after Settings, with a ``session.feature_toggled`` event.
"""

from __future__ import annotations

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Reviewee, Reviewer, ReviewSession
from ._quick_setup_refusal import refusal

OBSERVERS = b"ObserverEmail,ObserverName\nola@example.edu,Ola\n"
OBSERVERS_EMPTY = b"ObserverEmail,ObserverName\n"
REVIEWERS = b"ReviewerName,ReviewerEmail\nAl,al@example.edu\n"
REVIEWEES = b"RevieweeName,RevieweeEmail\nCy,cy@example.edu\n"
RELATIONSHIPS = b"ReviewerEmail,RevieweeEmail\nal@example.edu,cy@example.edu\n"


def _session(
    client: TestClient, db: Session, code: str, **toggles: bool
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    for field_name, value in toggles.items():
        setattr(rs, field_name, value)
    db.commit()
    return rs


def _submit_all(client: TestClient, rs: ReviewSession, **files: bytes):
    return client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/submit-all",
        data={"confirm_replace": "true"},
        files={
            f"{kind}_file": (f"{kind}.csv", payload, "text/csv")
            for kind, payload in files.items()
        },
        follow_redirects=False,
    )


def _toggled(db: Session, rs: ReviewSession) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == rs.id,
                AuditEvent.event_type == "session.feature_toggled",
            )
            .order_by(AuditEvent.id)
        ).scalars()
    )


def _bad_settings() -> bytes:
    """Parses, then fails ``apply_session_config``: an instrument with
    no name is a cross-row error only the apply finds."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    writer.writerow(("instruments[1].short_label", "X", "string"))
    return buf.getvalue().encode()


def _settings(observers_enabled: str) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    writer.writerow(("session.observers_enabled", observers_enabled, "boolean"))
    # Names the session's Default instrument, so the import keeps it
    # rather than asking first (findings S4).
    writer.writerow(("instruments[1].name", "Default", "string"))
    return buf.getvalue().encode()


def test_an_observers_upload_turns_observers_on(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "tabs-obs", observers_enabled=False)

    response = client.post(
        f"/operator/sessions/{rs.public_id}/quick-setup/observers",
        files={"file": ("o.csv", OBSERVERS, "text/csv")},
        follow_redirects=False,
    )

    assert "quick_setup_error" not in response.headers["location"]
    db.refresh(rs)
    assert rs.observers_enabled is True
    (event,) = _toggled(db, rs)
    assert event.detail["changes"] == {"observers_enabled": [False, True]}
    assert event.detail["reason"] == "quick_setup_upload"


def test_a_relationships_upload_turns_relationships_on(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "tabs-rel", relationships_enabled=False)

    response = _submit_all(
        client,
        rs,
        reviewers=REVIEWERS,
        reviewees=REVIEWEES,
        relationships=RELATIONSHIPS,
    )

    assert "quick_setup_error" not in response.headers["location"]
    db.refresh(rs)
    assert rs.relationships_enabled is True


def test_a_header_only_file_leaves_the_tab_off(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "tabs-empty", observers_enabled=False)

    response = _submit_all(client, rs, observers=OBSERVERS_EMPTY)

    # Saved — an empty roster — not refused, and still nothing turns on.
    assert "quick_setup_error" not in response.headers["location"]
    db.refresh(rs)
    assert rs.observers_enabled is False
    assert _toggled(db, rs) == []


def test_a_tab_already_on_writes_no_event(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "tabs-on", observers_enabled=True)

    _submit_all(client, rs, observers=OBSERVERS)

    assert _toggled(db, rs) == []


def test_a_refusal_inside_the_save_leaves_the_tab_off(
    client: TestClient, db: Session
) -> None:
    """The observers rows save, then a Settings error only the apply
    finds refuses the submit: the unit rolls back, toggle and event
    with it."""
    rs = _session(client, db, "tabs-refused", observers_enabled=False)

    response = _submit_all(
        client, rs, observers=OBSERVERS, settings=_bad_settings()
    )

    assert refusal(response).kind == "settings"
    db.expire_all()
    assert db.get(ReviewSession, rs.id).observers_enabled is False
    assert _toggled(db, rs) == []


def test_the_upload_wins_over_a_settings_file_turning_it_off(
    client: TestClient, db: Session
) -> None:
    """Settings applies first, then the tab turns on: a bundle saying
    ``observers_enabled=false`` cannot hide rows the same submit saved."""
    rs = _session(client, db, "tabs-settings", observers_enabled=True)

    response = _submit_all(
        client, rs, observers=OBSERVERS, settings=_settings("false")
    )

    assert "quick_setup_error" not in response.headers["location"]
    db.refresh(rs)
    assert rs.observers_enabled is True
    # On before the submit and on after it: no flip to record, though
    # Settings set it off on the way through.
    assert _toggled(db, rs) == []


def test_create_turns_observers_on_when_the_box_is_unticked(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "tabs-create"},
        files={"observers_file": ("o.csv", OBSERVERS, "text/csv")},
        follow_redirects=False,
    )

    assert "quick_setup_error" not in response.headers["location"]
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tabs-create")
    ).scalar_one()
    assert rs.observers_enabled is True
    assert len(_toggled(db, rs)) == 1


def test_the_rosters_without_a_tab_turn_nothing_on(
    client: TestClient, db: Session
) -> None:
    rs = _session(
        client, db, "tabs-none", observers_enabled=False, relationships_enabled=False
    )

    _submit_all(client, rs, reviewers=REVIEWERS, reviewees=REVIEWEES)

    db.refresh(rs)
    assert (rs.observers_enabled, rs.relationships_enabled) == (False, False)
    assert db.execute(select(Reviewer).where(Reviewer.session_id == rs.id)).first()
    assert db.execute(select(Reviewee).where(Reviewee.session_id == rs.id)).first()


def test_create_turns_relationships_on_when_the_box_is_unticked(
    client: TestClient, db: Session
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "tabs-create-rel"},
        files={
            "reviewers_file": ("r.csv", REVIEWERS, "text/csv"),
            "reviewees_file": ("e.csv", REVIEWEES, "text/csv"),
            "relationships_file": ("p.csv", RELATIONSHIPS, "text/csv"),
        },
        follow_redirects=False,
    )

    assert "quick_setup_error" not in response.headers["location"]
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tabs-create-rel")
    ).scalar_one()
    assert rs.relationships_enabled is True
    (event,) = _toggled(db, rs)
    assert event.detail["changes"] == {"relationships_enabled": [False, True]}


def test_a_toggle_turned_on_by_another_request_is_not_logged_again(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """The before-state is read under the session lock, which re-reads
    the row: a toggle another request turned on after this one loaded
    the session is already on, so no flip is logged (Codex on #3002)."""
    from sqlalchemy import update

    from app.services import session_guard
    from app.web.routes_operator import _quick_setup

    rs = _session(client, db, "tabs-race", observers_enabled=False)
    real_lock = session_guard.lock_session

    def racer_commits_first(db_, session_):
        # Another request's committed write, landing before this lock.
        db_.execute(
            update(ReviewSession)
            .where(ReviewSession.id == session_.id)
            .values(observers_enabled=True)
        )
        return real_lock(db_, session_)

    monkeypatch.setattr(
        _quick_setup.session_guard, "lock_session", racer_commits_first
    )

    _submit_all(client, rs, observers=OBSERVERS)

    db.refresh(rs)
    assert rs.observers_enabled is True
    assert _toggled(db, rs) == []
