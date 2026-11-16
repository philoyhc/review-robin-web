"""Segment 23E: a session another application created through the
handoff carries ``linked_app`` (`guide/archive/segment_23E_linked_sessions.md`),
and its profile turns off what that application does in Review Robin's
place: the release window, observers, the after-the-window visibility
cells, and the reviewee results warning.

The Utilities proof of concept links as Apply Desk will, so the idea can
be tried first.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentViewPolicy,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionTag,
)
from app.services import linked_apps, session_clone, session_config_io
from app.services import session_lifecycle as lifecycle
from app.services.validation import validate_session_setup
from app.web.views import (
    build_quick_setup_context,
    build_reviewer_visibility_rows,
    build_workflow_card_context,
)

from .test_handoffs import REVIEWEES, REVIEWERS, SETTINGS, _bundle, _post, _status


def _created(client: TestClient, db: Session, **changes: Any) -> tuple[ReviewSession, str]:
    bundle = _bundle(**changes)
    reply = _post(client, bundle)
    assert reply.status_code == 201, reply.text
    return db.scalars(select(ReviewSession)).one(), bundle["transfer_id"]


def test_a_handoff_from_a_known_application_links_the_draft(
    client: TestClient, db: Session
) -> None:
    review_session, transfer = _created(client, db)  # source_app "utilities"
    assert review_session.linked_app == "utilities"
    assert _status(client, transfer).json()["linked_app"] == "utilities"
    profile = linked_apps.profile_of(review_session)
    assert profile is not None and profile.shows_results == "Utilities"


def test_an_unknown_source_app_links_nothing(client: TestClient, db: Session) -> None:
    review_session, transfer = _created(client, db, source_app="somewhere-else")
    assert review_session.linked_app is None
    assert _status(client, transfer).json()["linked_app"] is None


def test_apply_desk_has_a_profile() -> None:
    profile = linked_apps.profile_for("applydesk")
    assert profile is not None and profile.name == "Apply Desk"
    assert profile.locks == frozenset(linked_apps.Lock)  # every lock


def test_the_switchboard_lets_a_profile_differ(client: TestClient, db: Session) -> None:
    """A profile is a set of named locks (23F rung 2a): Utilities keeps
    Review Robin's email on; a native session takes no lock."""
    review_session, _ = _created(client, db)
    utilities = linked_apps.profile_for("utilities")
    assert utilities is not None
    assert utilities.locks == frozenset(linked_apps.Lock) - {
        linked_apps.Lock.EMAIL,
        linked_apps.Lock.INVITATION_SEND,
    }
    assert utilities.has("release") and not utilities.has("email")
    assert linked_apps.locks(review_session, linked_apps.Lock.RELEASE)
    assert not linked_apps.locks(review_session, linked_apps.Lock.EMAIL)
    review_session.linked_app = None
    assert not any(linked_apps.locks(review_session, lock) for lock in linked_apps.Lock)


def test_session_home_shows_the_link_and_unlink_makes_it_native(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    home = f"/operator/sessions/{review_session.public_id}"
    page = client.get(home).text
    assert 'data-linked-app="utilities"' in page  # Session details' chip
    assert "Linked: Utilities</span>" in page  # the status row's pill
    assert "Session is linked with" in page
    # The Linked application card holds Unlink (rung 5b; inert in 5a).
    assert 'id="linked-app-card"' in page
    assert "data-linked-app-unlink" not in page
    reply = client.post(f"{home}/unlink", follow_redirects=False)
    assert reply.status_code == 303
    db.refresh(review_session)
    assert review_session.linked_app is None
    after = client.get(home).text
    assert "data-linked-app" not in after and "data-linked-pill" not in after
    assert 'id="linked-app-card"' not in after
    event = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.unlinked")).one()
    assert event.detail is not None and event.detail["changes"]["linked_app"] == [
        "utilities",
        None,
    ]
    # A second Unlink writes nothing.
    client.post(f"{home}/unlink", follow_redirects=False)
    assert (
        len(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.unlinked")).all())
        == 1
    )


def test_a_copy_is_native(client: TestClient, db: Session) -> None:
    """Only the handoff links: a Duplicate never carries the mark."""
    review_session, _ = _created(client, db)
    copy = session_clone.clone_session(
        db, source=review_session, user=review_session.created_by_user, mode="all"
    )
    assert copy.linked_app is None


# ── Rung 3: the profile's effects ─────────────────────────────────────


def _expired_with_release(db: Session, review_session: ReviewSession) -> None:
    """Close the session with a release anchor already reached, as no
    linked control can set it: the window would be open on a native one."""
    review_session.status = "expired"
    review_session.responses_release_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()


def test_the_release_window_never_opens_on_a_linked_session(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    _expired_with_release(db, review_session)
    assert not lifecycle.is_response_release_window_open(review_session)
    review_session.linked_app = None  # as Unlink leaves it
    assert lifecycle.is_response_release_window_open(review_session)


def test_the_workflow_card_offers_no_release(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    review_session.status = "expired"
    db.commit()
    card = build_workflow_card_context(db, review_session, return_to="")
    assert not card["release_responses_visible"] and not card["stop_release_visible"]
    reply = client.post(
        f"/operator/sessions/{review_session.public_id}/workflow/release-responses",
        follow_redirects=False,
    )
    assert reply.status_code == 303 and "super_error=linked_release" in reply.headers["location"]
    db.refresh(review_session)
    assert review_session.responses_release_at is None


def test_session_details_shows_release_and_observers_off(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    page = client.get(f"/operator/sessions/{review_session.public_id}").text
    assert page.count("Off: see in Utilities") == 2
    assert 'name="responses_release_at"' not in page
    assert 'name="responses_release_until"' not in page
    assert "data-observers-off" in page and 'name="observers_enabled"' not in page


def _save(client: TestClient, review_session: ReviewSession, **form: str) -> int:
    return client.post(
        f"/operator/sessions/{review_session.public_id}/config",
        data={
            "name": review_session.name,
            "code": review_session.code,
            "display_timezone": review_session.display_timezone or "UTC",
            **form,
        },
        follow_redirects=False,
    ).status_code


def test_the_details_save_refuses_release_and_observers(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With the details lock (23F) the card's Save is refused whole; a
    profile without it still refuses release and observers (23E)."""
    review_session, _ = _created(client, db)
    assert _save(client, review_session) == 409
    utilities = linked_apps.LINKED_APPS["utilities"]
    monkeypatch.setitem(
        linked_apps.LINKED_APPS,
        "utilities",
        dataclasses.replace(utilities, locks=utilities.locks - {linked_apps.Lock.SESSION_DETAILS}),
    )
    assert _save(client, review_session, responses_release_at="2030-01-01 09:00") == 422
    assert _save(client, review_session, observers_enabled="true") == 422
    assert _save(client, review_session) == 303  # the card's own Save
    db.refresh(review_session)
    assert review_session.responses_release_at is None and not review_session.observers_enabled


def _import(review_session: ReviewSession, csv_rows: list[list[str]]) -> list[str]:
    rows, errors = session_config_io.split_rows(csv_rows)
    return [error.field for error in errors] + [
        error.field for error in session_config_io.validate_session_config(review_session, rows)
    ]


def test_a_settings_import_refuses_release_values_and_observers(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    refused = _import(
        review_session,
        [
            ["session.responses_release_at", "2030-01-01T09:00:00+00:00", "datetime"],
            ["session.observers_enabled", "true", "boolean"],
        ],
    )
    assert refused == ["session.responses_release_at", "session.observers_enabled"]
    # Blank release rows pass: the session's own export imports back.
    assert _import(review_session, [["session.responses_release_at", "", "datetime"]]) == []


def test_a_linked_handoff_refuses_an_observers_file(client: TestClient, db: Session) -> None:
    observers = "ObserverEmail,ObserverName\r\nolu@example.edu,Olu\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "observers": observers}
    reply = _post(client, _bundle(files=files))
    assert reply.status_code == 422
    body = reply.json()
    assert (body["error"], body["slot"], body["reason"]) == (
        "invalid_setup",
        "observers",
        "observers_off",
    )
    assert db.scalars(select(ReviewSession)).first() is None


def test_a_linked_handoffs_settings_may_not_release(client: TestClient, db: Session) -> None:
    release = "session.responses_release_at,2030-01-01T09:00:00+00:00,datetime\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": SETTINGS + release}
    reply = _post(client, _bundle(files=files))
    assert reply.status_code == 422 and reply.json()["slot"] == "settings"
    assert db.scalars(select(ReviewSession)).first() is None


def test_the_visibility_card_names_the_application(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db, files=_with_settings())
    instruments = list(db.scalars(select(Instrument)))
    rows = build_reviewer_visibility_rows(db, instruments)[instruments[0].id]
    assert [row["after_release_label"] for row in rows] == ["See in Utilities"] * 2
    assert all(row["after_release_mode"] == "" for row in rows)
    page = client.get(f"/operator/sessions/{review_session.public_id}/instruments").text
    assert "See in Utilities" in page
    assert "data-new-model-vp-observers-row" not in page


def _with_settings() -> dict[str, str]:
    return {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": SETTINGS}


def test_the_collation_page_is_closed(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    # Every control refuses this state; set directly to show the gate holds.
    review_session.observers_enabled = True
    review_session.status = "ready"
    db.add(Observer(session_id=review_session.id, email="alice@example.edu", display_name="A"))
    db.commit()
    url = f"/me/sessions/{review_session.public_id}/collation"
    assert client.get(url).status_code == 404
    review_session.linked_app = None
    db.commit()
    assert client.get(url).status_code == 200  # the gate, not the roster


def test_validate_raises_no_unreachable_results_warning(client: TestClient, db: Session) -> None:
    """The bundle's reviewees are keyed by dossier, not mail: a native
    session warns, a linked one does not."""
    review_session, _ = _created(client, db)

    def fields() -> set[str]:
        return {
            f"{issue.source}.{issue.field}" for issue in validate_session_setup(db, review_session)
        }

    assert "reviewees.email_or_identifier" not in fields()
    review_session.linked_app = None
    assert "reviewees.email_or_identifier" in fields()


def test_the_results_page_is_closed_until_unlink(client: TestClient, db: Session) -> None:
    """A reviewee granted Raw after release, the window's anchor reached:
    404 while linked, the page once Unlink makes the session native."""
    review_session, _ = _created(client, db, files=_with_settings())
    instrument = db.scalars(select(Instrument)).one()
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            after_release_granularity="row",
            after_release_identification="identified",
        )
    )
    db.add(
        Reviewee(session_id=review_session.id, name="Al", email_or_identifier="alice@example.edu")
    )
    _expired_with_release(db, review_session)
    url = f"/me/sessions/{review_session.public_id}/results"
    assert client.get(url).status_code == 404
    home = f"/operator/sessions/{review_session.public_id}"
    assert client.post(f"{home}/unlink", follow_redirects=False).status_code == 303
    assert client.get(url).status_code == 200


def test_stop_release_is_refused_by_route_and_service(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    review_session.status = "expired"
    db.commit()
    reply = client.post(
        f"/operator/sessions/{review_session.public_id}/workflow/stop-release",
        follow_redirects=False,
    )
    assert "super_error=linked_release" in reply.headers["location"]
    db.refresh(review_session)
    assert review_session.responses_release_until is None
    user = review_session.created_by_user
    for service in (lifecycle.release_responses_now, lifecycle.stop_responses_release):
        with pytest.raises(lifecycle.SessionStateConflict):
            service(db, review_session=review_session, user=user)


def test_quick_setup_offers_and_takes_no_observers(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    slots = {slot.key for slot in build_quick_setup_context(db, review_session).slots}
    assert "observers" not in slots
    client.post(
        f"/operator/sessions/{review_session.public_id}/quick-setup/observers",
        files={"file": ("obs.csv", b"ObserverName,ObserverEmail\nOren,oren@example.edu\n")},
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert not review_session.observers_enabled
    assert db.scalars(select(Observer)).first() is None


def test_a_transfer_from_before_the_link_still_replays(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transfer completed before 23E, observers file and all, answers
    ``already_created`` on a retry rather than the new refusal (Codex)."""
    observers = "ObserverEmail,ObserverName\r\nolu@example.edu,Olu\r\n"
    bundle = _bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES, "observers": observers})
    with monkeypatch.context() as before_23e:
        before_23e.setattr(linked_apps, "LINKED_APPS", {})
        assert _post(client, bundle).status_code == 201
    again = _post(client, bundle)
    assert again.status_code == 200 and again.json()["status"] == "already_created"
    assert db.scalars(select(ReviewSession)).one().linked_app is None


# ── 23F rung 5: the Linked application card and the session locks ─────


def test_session_details_never_unlock_and_the_card_holds_unlink(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    page = client.get(f"/operator/sessions/{review_session.public_id}?editing=1").text
    assert 'data-config-mode="display"' in page  # ?editing=1 does not unlock it
    assert "data-details-locked" in page
    assert "data-linked-app-card" in page and "/unlink" in page
    assert 'id="quick-setup-reviewers"' not in page
    review_session.linked_app = None
    db.commit()
    native = client.get(f"/operator/sessions/{review_session.public_id}?editing=1").text
    assert 'data-config-mode="edit"' in native and "data-linked-app-card" not in native


def test_quick_setup_and_the_settings_import_are_refused(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    base = f"/operator/sessions/{review_session.public_id}/quick-setup"
    reviewers = b"ReviewerName,ReviewerEmail\nZed,zed@example.edu\n"
    reply = client.post(f"{base}/reviewers", files={"file": ("r.csv", reviewers)})
    assert reply.status_code == 409
    assert "zed@example.edu" not in set(db.scalars(select(Reviewer.email)))


def test_the_lobby_refuses_a_linked_sessions_details_and_tags(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    reply = client.post(
        f"/operator/sessions/{review_session.public_id}/lobby-edit",
        data={"name": "Renamed", "code": review_session.code, "tags": "x"},
        follow_redirects=False,
    )
    assert reply.status_code == 409
    client.post(
        "/operator/sessions/bulk-tags",
        data={"session_ids": [review_session.id], "tags": "bulk", "op": "add"},
        follow_redirects=False,
    )
    db.expire_all()
    assert review_session.name != "Renamed"
    assert not list(db.scalars(select(SessionTag)))
    lobby = client.get("/operator/sessions").text
    assert 'data-linked="Utilities"' in lobby


# ── 23F rung 6: the roster and email locks, and the defaults ───────────


def test_the_roster_pages_are_read_only(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    base = f"/operator/sessions/{review_session.public_id}"
    for page in ("reviewers", "reviewees", "relationships"):
        text = client.get(f"{base}/{page}").text
        assert "data-rosters-linked" in text and "come from Utilities" in text, page
        # A revisited editor URL opens no editor (Codex on #3924).
        editor = client.get(f"{base}/{page}?add=1").text
        assert f"Add new {page[:-1]}" not in editor, page
    # The self-fields cards stay Review Robin's: on the page, not in a panel.
    for page, card in (("reviewers", "reviewer"), ("reviewees", "reviewee")):
        text = client.get(f"{base}/{page}").text
        assert "data-linked-self-fields" in text and f'id="{card}-self-fields-form"' in text
        assert 'id="roster-unlock-panel"' not in text
    reply = client.post(f"{base}/reviewers/self-fields", data={"fields": ["name"]})
    assert reply.status_code in (200, 303), reply.text
    reviewer_id = db.scalars(select(Reviewer.id)).first()
    editor = client.get(f"{base}/reviewers?edit_id={reviewer_id}").text
    assert "Edit reviewer" not in editor
    writes = [
        ("reviewers/create", {"name": "Zed", "email": "zed@example.edu"}),
        ("reviewees/create", {"name": "Zoe", "email_or_identifier": "SCH27-9999"}),
        ("reviewers/delete-all", {"confirm": "true"}),
    ]
    for path, data in writes:
        reply = client.post(f"{base}/{path}", data=data, follow_redirects=False)
        assert reply.status_code == 409, path
    reply = client.post(
        f"{base}/reviewers/import",
        files={"file": ("r.csv", b"ReviewerName,ReviewerEmail\nZed,zed@example.edu\n")},
        follow_redirects=False,
    )
    assert reply.status_code == 409
    assert "zed@example.edu" not in set(db.scalars(select(Reviewer.email)))


def test_relationships_are_on_from_the_create(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db)
    assert review_session.relationships_enabled


def test_apply_desk_sends_its_own_email_and_utilities_keeps_review_robins(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Utilities keeps the email locks off (the switchboard's second
    profile); Apply Desk takes them."""
    review_session, _ = _created(client, db)
    base = f"/operator/sessions/{review_session.public_id}"
    assert "/setup-invite" in client.get(base).text  # Utilities: email on
    assert client.get(f"{base}/setup-invite").status_code == 200
    review_session.linked_app = "applydesk"
    db.commit()
    home = client.get(base).text
    assert f'href="{base}/setup-invite"' not in home
    assert client.get(f"{base}/setup-invite").status_code == 409
    for path in ("invitations/send-all", "invitations/remind-incomplete"):
        assert client.post(f"{base}/{path}", follow_redirects=False).status_code == 409, path
    review_session.status = "ready"
    db.commit()
    card = build_workflow_card_context(db, review_session, return_to="")
    assert not card["send_invites_visible"] and not card["send_reminders_visible"]
