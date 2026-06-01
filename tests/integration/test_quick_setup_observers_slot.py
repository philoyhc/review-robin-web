"""Integration coverage for the Quick Setup Observers slot.

Closes W12 from `guide/participant_model_remainder.md`: gates the
Observers slot on the session's ``observers_enabled`` toggle,
shipped end-to-end through the per-slot POST + the consolidated
submit-all chain. Mirrors the Relationships slot pattern (PR 7c)
— file-upload mode, ``needs_confirm`` on replace, lifecycle gate
on Activated sessions, no response-loss acknowledgement (observers
don't cascade delete responses).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Observer, ReviewSession
from app.web import views


OBSERVER_CSV = (
    b"ObserverName,ObserverEmail,ObserverTag1\n"
    b"Oren,oren@example.edu,Mentor\n"
)


def _make_session(
    client: TestClient,
    db: Session,
    *,
    code: str,
    observers_enabled: bool = True,
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "QSObs", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    review_session.observers_enabled = observers_enabled
    db.commit()
    return review_session


# ---------------------------------------------------------------------------
# View-shape tests
# ---------------------------------------------------------------------------


def test_observers_slot_renders_only_when_toggle_on(
    client: TestClient, db: Session
) -> None:
    """The Observers slot is suppressed when the session's
    ``observers_enabled`` toggle is off (default) and appears
    between Relationships and Session settings on the right
    column when on."""
    rs_off = _make_session(
        client, db, code="qsobs-off", observers_enabled=False
    )
    context_off = views.build_quick_setup_context(db, rs_off)
    assert [s.key for s in context_off.slots] == [
        "reviewers",
        "reviewees",
        "relationships",
        "settings",
    ]

    rs_on = _make_session(client, db, code="qsobs-on")
    context_on = views.build_quick_setup_context(db, rs_on)
    assert [s.key for s in context_on.slots] == [
        "reviewers",
        "reviewees",
        "relationships",
        "observers",
        "settings",
    ]
    by_key = {s.key: s for s in context_on.slots}
    assert by_key["observers"].is_wired is True
    assert by_key["observers"].mode == "file_upload"
    assert by_key["observers"].wire_url == (
        f"/operator/sessions/{rs_on.id}/quick-setup/observers"
    )


def test_observers_slot_count_reflects_population(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsobs-count")
    context_empty = views.build_quick_setup_context(db, review_session)
    by_key = {s.key: s for s in context_empty.slots}
    assert by_key["observers"].count == 0

    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    context_after = views.build_quick_setup_context(db, review_session)
    by_key_after = {s.key: s for s in context_after.slots}
    assert by_key_after["observers"].count == 1


# ---------------------------------------------------------------------------
# Per-slot route
# ---------------------------------------------------------------------------


def test_observers_route_imports_rows(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsobs-route")

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("#quick-setup-observers")

    rows = db.execute(
        select(Observer).where(Observer.session_id == review_session.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].display_name == "Oren"
    assert rows[0].tag_1 == "Mentor"


def test_observers_route_replace_requires_confirm(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="qsobs-confirm")

    # First upload populates.
    client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    # Second upload without confirm should redirect with needs_confirm.
    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "quick_setup_error=observers" in location
    assert "quick_setup_reason=needs_confirm" in location


def test_observers_lifecycle_gate_on_ready(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    """An Activated session rejects observers uploads with the
    ``lifecycle`` reason token. Mirrors the relationships /
    reviewers / reviewees guards."""
    from app.services import session_lifecycle as lifecycle

    operator = make_client(alice)
    operator.post(
        "/operator/sessions",
        data={"name": "Locked", "code": "qsobs-lifecycle"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "qsobs-lifecycle")
    ).scalar_one()
    review_session.observers_enabled = True
    review_session.status = lifecycle.SessionStatus.ready.value
    db.commit()

    response = operator.post(
        f"/operator/sessions/{review_session.id}/quick-setup/observers",
        files={"file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_reason=lifecycle" in response.headers["location"]


# ---------------------------------------------------------------------------
# Submit-all chain
# ---------------------------------------------------------------------------


def test_submit_all_runs_observers_branch(
    client: TestClient, db: Session
) -> None:
    """``submit-all`` with only an observers file imports them and
    redirects to the observers fragment. No other slot needs to be
    attached for the branch to fire."""
    review_session = _make_session(client, db, code="qsobs-chain")

    response = client.post(
        f"/operator/sessions/{review_session.id}/quick-setup/submit-all",
        files={"observers_file": ("obs.csv", OBSERVER_CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("#quick-setup-observers")

    rows = db.execute(
        select(Observer).where(Observer.session_id == review_session.id)
    ).scalars().all()
    assert len(rows) == 1
