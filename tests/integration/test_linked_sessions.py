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
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentDisplayField,
    InstrumentViewPolicy,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionTag,
)
from app.services import field_labels, linked_apps, session_clone, session_config_io
from app.services import instruments as instruments_service
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
    # Hidden on a linked session (author, 2026-11-16): the card never unlocks.
    assert "Release responses from" not in page and "Release responses until" not in page
    # Utilities keeps Review Robin's email, so its prompts stay; Apply
    # Desk's sessions take the email lock and hide them.
    assert 'name="invite_offsets"' in page and 'name="reminder_offsets"' in page
    review_session.linked_app = "applydesk"
    db.commit()
    page = client.get(f"/operator/sessions/{review_session.public_id}").text
    assert 'name="invite_offsets"' not in page and 'name="reminder_offsets"' not in page
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
    # No self-fields cards: a linked session's roster tags are unused
    # (author, 2026-11-16), and their saves are locked with the rosters.
    for page, card in (("reviewers", "reviewer"), ("reviewees", "reviewee")):
        text = client.get(f"{base}/{page}").text
        assert f'id="{card}-self-fields-form"' not in text, page
        reply = client.post(
            f"{base}/{page}/self-fields", data={"fields": ["name"]}, follow_redirects=False
        )
        assert reply.status_code == 409, page
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


# ── 23F rung 7a: the instrument ────────────────────────────────────────


def test_the_create_fixes_the_rule_and_the_display_default(client: TestClient, db: Session) -> None:
    """One instrument, its rule fixed by Review Robin (assign where a
    relationship exists), its display fields starting from the dossier
    link."""
    review_session, _ = _created(client, db, files=_with_settings())
    instrument = db.scalars(select(Instrument)).one()
    assert set(instrument.band1_touched_links or []) == {"link1", "link2", "link3"}
    assert instrument.group_kind is None
    state = instruments_service.decode_band1_state(instrument, db)
    assert state["link1"]["mode"] == "all"
    assert state["link2"]["mode"] == "filter"
    assert [(r["field"], r["op"]) for r in state["link2"]["rules"]] == [
        ("pair_context.tag1", "IS FILLED")
    ]
    shown = {
        (f.source_type, f.source_field)
        for f in db.scalars(
            select(InstrumentDisplayField).where(
                InstrumentDisplayField.instrument_id == instrument.id
            )
        )
    }
    assert ("reviewee", "profile_link") in shown
    assert not {s for s in shown if s[1].startswith("tag_")}


def test_a_create_making_two_instruments_is_refused(client: TestClient, db: Session) -> None:
    second = (
        "instruments[2].name,Second look,string\r\n"
        "instruments[2].response_fields[1].field_key,note,string\r\n"
        "instruments[2].response_fields[1].label,Note,string\r\n"
        "instruments[2].response_fields[1].response_type,text,string\r\n"
        "instruments[2].response_fields[1].data_type,String,string\r\n"
    )
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": SETTINGS + second}
    reply = _post(client, _bundle(files=files))
    assert reply.status_code == 422 and reply.json()["reason"] == "one_instrument"
    assert db.scalars(select(ReviewSession)).first() is None


def test_a_replay_of_a_cut_off_create_sets_the_instrument_up(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A create cut off after its rosters saved, before the instrument
    set-up, gets the set-up from its replay, with the record (the cold
    read of 23F)."""
    from app.services import handoffs

    real = handoffs.set_up_instrument
    calls: list[int] = []

    def dies_first(*args: Any) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("cut off")
        real(*args)

    monkeypatch.setattr(handoffs, "set_up_instrument", dies_first)
    bundle = _bundle(files=_with_settings())
    with pytest.raises(RuntimeError):
        _post(client, bundle)
    db.rollback()
    again = _post(client, bundle)
    assert again.status_code == 200 and again.json()["status"] == "already_created"
    instrument = db.scalars(select(Instrument)).one()
    db.refresh(instrument)
    assert set(instrument.band1_touched_links or []) == {"link1", "link2", "link3"}
    state = instruments_service.decode_band1_state(instrument, db)
    assert state["link2"]["mode"] == "filter"


# --- Segment 23F rung 7c: the Instruments page locks ---------------------


def _base(review_session: ReviewSession) -> str:
    return f"/operator/sessions/{review_session.public_id}/instruments"


@pytest.mark.parametrize(
    "path",
    [
        "/add-new-model",
        "/{id}/replicate",
        "/{id}/page-break/create",
        "/{id}/fields/add-row",
    ],
)
def test_the_structure_routes_refuse_a_linked_instrument(
    client: TestClient, db: Session, path: str
) -> None:
    review_session, _ = _created(client, db, files=_with_settings())
    instrument = db.scalars(select(Instrument)).one()
    reply = client.post(_base(review_session) + path.format(id=instrument.id), data={})
    assert reply.status_code == 409, reply.text
    assert "linked to Utilities" in reply.text
    assert len(db.scalars(select(Instrument)).all()) == 1


def test_the_identity_route_refuses_a_linked_instrument(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db, files=_with_settings())
    instrument = db.scalars(select(Instrument)).one()
    reply = client.post(
        f"{_base(review_session)}/{instrument.id}/identity", json={"short_label": "Mine"}
    )
    assert reply.status_code == 409


def test_the_save_keeps_the_owned_parts_and_writes_the_rest(
    client: TestClient, db: Session
) -> None:
    """The card's Save on a linked instrument writes what is Review
    Robin's (here the display layout) and leaves the rule, the identity and
    the response fields as the application set them."""
    review_session, _ = _created(client, db, files=_with_settings())
    instrument = db.scalars(select(Instrument)).one()
    rule_before = instruments_service.decode_band1_state(instrument, db)
    label_before = instrument.short_label
    keys_before = [f.field_key for f in sorted(instrument.response_fields, key=lambda f: f.order)]
    reply = client.post(
        f"{_base(review_session)}/{instrument.id}/save",
        data={
            "link2_mode": "all",
            "short_label": "Renamed",
            "description": "Mine now",
            "display_layout": "stacked",
            "band2_state_snapshot": '{"response_fields": []}',
        },
    )
    assert reply.status_code == 200, reply.text
    db.expire_all()
    instrument = db.scalars(select(Instrument)).one()
    assert instrument.display_layout == "stacked"
    assert instrument.short_label == label_before and instrument.description != "Mine now"
    assert instruments_service.decode_band1_state(instrument, db) == rule_before
    assert [
        f.field_key for f in sorted(instrument.response_fields, key=lambda f: f.order)
    ] == keys_before


def test_the_page_shows_the_instrument_fixed(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db, files=_with_settings())
    page = client.get(_base(review_session)).text
    assert "data-linked-rule" in page and "data-linked-fields" in page
    assert "+Instrument</button>" not in page and ">Replicate</button>" not in page
    assert "+Page break</button>" not in page


def test_a_native_page_keeps_its_structure_controls(client: TestClient, db: Session) -> None:
    review_session, _ = _created(client, db, source_app="otherapp", files=_with_settings())
    page = client.get(_base(review_session)).text
    assert "data-linked-rule" not in page and "+Instrument</button>" in page


def test_the_mock_bundle_arrives_paired_and_in_its_timezone(
    client: TestClient, db: Session
) -> None:
    """Utilities' proof of concept (segment 23F, author 2026-11-16): no
    roster tags, every pair related and tagged, and Asia/Singapore."""
    from app.db.models import Relationship
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    assert review_session.display_timezone == "Asia/Singapore"
    pairs = db.scalars(select(Relationship)).all()
    assert len(pairs) == len(people) * len(mock.APPLICATIONS)
    assert all(pair.tag_1 for pair in pairs)
    assert not any(r.tag_1 for r in db.scalars(select(Reviewer)))
    db.refresh(review_session)
    assert field_labels.resolve(review_session, "pair_context", "1") == "Apply-Desk-Link"


def test_the_page_seeds_no_display_field_back(client: TestClient, db: Session) -> None:
    """The Instruments page's display-field repair adds none back on a
    linked instrument: the relationship's tag (Apply-Desk-Link) and the
    roster columns the create trimmed stay off (author, 2026-11-16)."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    client.get(_base(review_session))
    db.expire_all()
    sources = {(f.source_type, f.source_field) for f in db.scalars(select(InstrumentDisplayField))}
    assert not any(kind == "pair_context" for kind, _ in sources)
    assert ("reviewee", "profile_link") in sources


def test_the_mock_create_arrives_filled(client: TestClient, db: Session) -> None:
    """Every part the application owns arrives with the create (author,
    2026-11-16): the session's fields and the gate's instrument."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    assert review_session.description and review_session.help_contact
    assert review_session.scheduled_activate_at and review_session.deadline
    assert sorted(t.tag for t in db.scalars(select(SessionTag))) == ["2027", "applydesk"]
    instrument = db.scalars(select(Instrument)).one()
    assert (instrument.name, instrument.description) == (mock.INSTRUMENT, mock.GATE_DESCRIPTION)
    assert instrument.short_label == mock.INSTRUMENT
    assert all(f.help_text and f.help_text_visible for f in instrument.response_fields)


def test_the_mock_says_which_fields_are_required(client: TestClient, db: Session) -> None:
    """Whether a field is required is the application's (author,
    2026-11-16): the mock's score is, its comment is not."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    _created(client, db, files=mock.bundle(people)["files"])
    fields = {f.field_key: f.required for f in db.scalars(select(Instrument)).one().response_fields}
    assert fields == {"score": True, "comment": False}


def _profile_shown(db: Session) -> bool:
    db.expire_all()
    return any(
        f.source_field == "profile_link" and f.visible
        for f in db.scalars(select(InstrumentDisplayField))
    )


@pytest.mark.parametrize("route", ["save", "band2-state"])
def test_the_dossier_links_display_is_held(client: TestClient, db: Session, route: str) -> None:
    """Profile is the application's on a linked instrument (author,
    2026-11-16): a Save that unticks it, through the card's Save or the
    Band 2 route, leaves it shown."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    instrument = db.scalars(select(Instrument)).one()
    assert _profile_shown(db)
    state = {"selected_display_keys": ["reviewee.name", "reviewee.email_or_identifier"]}
    url = f"{_base(review_session)}/{instrument.id}/{route}"
    if route == "save":
        reply = client.post(
            url, data={"link2_mode": "all", "band2_state_snapshot": json.dumps(state)}
        )
    else:
        reply = client.post(url, json=state)
    assert reply.status_code == 200, reply.text
    assert _profile_shown(db)


def test_the_page_shows_profile_held_and_the_structure_fixed(
    client: TestClient, db: Session
) -> None:
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    page = client.get(_base(review_session)).text
    row = page.split('data-source-field="profile_link"')[1].split("</tr>")[0]
    assert 'data-held="true"' in row and "disabled" in row and "Set by Utilities" in row
    assert "box.disabled = locked || off || row.getAttribute('data-held') === 'true';" in page


@pytest.mark.parametrize("action", ["edit", "delete", "add"])
def test_the_per_field_routes_refuse_the_dossier_link(
    client: TestClient, db: Session, action: str
) -> None:
    """The per-field display routes cannot hide, remove or re-add Profile
    on a linked instrument (the cold read of 23F rung 7h)."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    instrument = db.scalars(select(Instrument)).one()
    profile = next(f for f in instrument.display_fields if f.source_field == "profile_link")
    base = f"{_base(review_session)}/{instrument.id}/display-fields"
    if action == "add":
        reply = client.post(base, data={"source_pair": "reviewee:profile_link"})
    else:
        reply = client.post(f"{base}/{profile.id}/{action}", data={})
    assert reply.status_code == 409, reply.text
    assert _profile_shown(db)


def test_a_crafted_tick_shows_no_hidden_dossier_link(client: TestClient, db: Session) -> None:
    """The hold works both ways: a Save cannot tick a hidden Profile on."""
    from utilityapps.interop_poc import mock

    people = mock.reviewers("Admin", "admin@example.edu")
    review_session, _ = _created(client, db, files=mock.bundle(people)["files"])
    instrument = db.scalars(select(Instrument)).one()
    for field in instrument.display_fields:
        if field.source_field == "profile_link":
            field.visible = False
    db.commit()
    # Padded, as `set_band2_state` strips it (Codex on #3932).
    keys = ["reviewee.name", "reviewee.email_or_identifier", " reviewee.profile_link "]
    reply = client.post(
        f"{_base(review_session)}/{instrument.id}/band2-state",
        json={"selected_display_keys": keys},
    )
    assert reply.status_code == 200, reply.text
    assert not _profile_shown(db)
