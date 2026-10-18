"""Unit tests for the return-to-origin helper (Segment 11D, PR A)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.web.return_to import (
    DEFAULT_TARGET,
    PARTICIPANT_DEFAULT,
    ReturnTarget,
    resolve_return_to,
)


def _seed_session(db: Session, *, name: str = "Spring 2026") -> ReviewSession:
    """A session owned by ``op@example.edu`` (see :func:`_owner`)."""
    user = User(email="op@example.edu", display_name="Op", is_operator=True)
    db.add(user)
    db.flush()
    session = ReviewSession(name=name, code="rrw-test", created_by_user_id=user.id)
    db.add(session)
    db.flush()
    db.add(SessionOperator(session_id=session.id, user_id=user.id))
    db.flush()
    return session


def _owner(db: Session, session: ReviewSession) -> User:
    return db.get(User, session.created_by_user_id)


def _user(db: Session, email: str, *, is_sys_admin: bool = False) -> User:
    user = User(email=email, display_name=email, is_sys_admin=is_sys_admin)
    db.add(user)
    db.flush()
    return user


def test_none_falls_back_to_default(db: Session) -> None:
    assert resolve_return_to(None, db, viewer=None) == PARTICIPANT_DEFAULT


def test_empty_string_falls_back_to_default(db: Session) -> None:
    assert resolve_return_to("", db, viewer=None) == PARTICIPANT_DEFAULT


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"is_operator": True}, DEFAULT_TARGET),
        ({"is_sys_admin": True}, DEFAULT_TARGET),
        ({}, PARTICIPANT_DEFAULT),
    ],
)
def test_the_fallback_is_the_lobby_for_operators_and_me_for_others(
    db: Session, flags: dict[str, bool], expected: ReturnTarget
) -> None:
    """Participant audit M8: a participant sent to the Sessions lobby is
    only bounced to ``/me``, so their fallback is ``/me`` itself."""
    viewer = User(email="v@example.edu", display_name="V", **flags)
    db.add(viewer)
    db.flush()
    assert resolve_return_to(None, db, viewer=viewer) == expected
    assert resolve_return_to("https://evil.example.com", db, viewer=viewer) == expected


def test_operator_sessions_root_resolves_to_sessions_label(db: Session) -> None:
    target = resolve_return_to("/operator/sessions", db, viewer=None)
    assert target.url == "/operator/sessions"
    assert target.label == "Sessions"


def test_operator_session_detail_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="My Review")
    target = resolve_return_to(
        f"/operator/sessions/{session.public_id}", db, viewer=_owner(db, session)
    )
    assert target.url == f"/operator/sessions/{session.public_id}"
    assert target.label == "My Review"


def test_operator_session_tab_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="Tabbed Session")
    target = resolve_return_to(
        f"/operator/sessions/{session.public_id}/instruments",
        db,
        viewer=_owner(db, session),
    )
    assert target.url == f"/operator/sessions/{session.public_id}/instruments"
    assert target.label == "Tabbed Session"


def test_operator_session_with_unknown_id_falls_back(db: Session) -> None:
    assert resolve_return_to("/operator/sessions/999999", db, viewer=None) == PARTICIPANT_DEFAULT


def test_reviewer_root_resolves_to_your_reviews(db: Session) -> None:
    target = resolve_return_to("/me", db, viewer=None)
    assert target.url == "/me"
    assert target.label == "your reviews"


def test_reviewer_session_resolves_to_session_name(db: Session) -> None:
    session = _seed_session(db, name="Reviewer Session")
    target = resolve_return_to(
        f"/me/sessions/{session.public_id}", db, viewer=_owner(db, session)
    )
    assert target.url == f"/me/sessions/{session.public_id}"
    assert target.label == "Reviewer Session"


def test_query_string_and_fragment_are_stripped(db: Session) -> None:
    target = resolve_return_to("/operator/sessions?validated=1#x", db, viewer=None)
    assert target.url == "/operator/sessions"
    assert target.label == "Sessions"


@pytest.mark.parametrize(
    "raw",
    [
        "https://evil.example.com/",
        "//evil.example.com/path",
        "/operator/../etc/passwd",
        "/operator/sessions/abc",  # non-numeric session id
        "/operator/instruments",  # not in the allowlist
        "javascript:alert(1)",
        # ``$`` matched before a trailing newline, which a cookie then
        # refused with a 500.
        "/operator/sessions\n",
        "/operator/sessions%0A",
        "/me\n",
        "/operator/settings\n",
    ],
)
def test_paths_outside_allowlist_fall_back_to_default(
    db: Session, raw: str
) -> None:
    assert resolve_return_to(raw, db, viewer=None) == PARTICIPANT_DEFAULT


def test_operator_session_page_at_any_depth_resolves_to_session_name(
    db: Session,
) -> None:
    session = _seed_session(db, name="Deep Session")
    path = f"/operator/sessions/{session.public_id}/instruments/7"
    target = resolve_return_to(path, db, viewer=_owner(db, session))
    assert target.url == path
    assert target.label == "Deep Session"


@pytest.mark.parametrize(
    ("path", "label"),
    [
        ("/operator/sessions/archived", "Archived sessions"),
        ("/operator/sessions/new", "New session"),
        ("/operator/settings", "Settings"),
        ("/operator/settings/", "Settings"),
    ],
)
def test_operator_pages_outside_a_session_resolve_to_their_title(
    db: Session, path: str, label: str
) -> None:
    assert resolve_return_to(path, db, viewer=None) == ReturnTarget(url=path, label=label)


def _fullwidth(text: str) -> str:
    """Each ASCII digit or lowercase letter as its fullwidth form."""
    return "".join(chr(ord(c) + 0xFEE0) for c in text)


@pytest.mark.parametrize(
    "shape",
    [
        "/operator/sessions/{id}/a.b",  # outside the segment alphabet
        "/operator/sessions/{id}\n",  # ``$`` matched before a newline
        "/operator/sessions/{id}/instruments\n",
        "/operator/sessions/{fw}",  # ``\d`` / ``\w`` matched any Unicode form
        "/operator/sessions/{fw}/assignments",
        "/me/sessions/{fw}",
        # A page a POST rendered: the chrome passes the POST's path, and
        # a GET there would 405.
        "/operator/sessions/{id}/reviewers/import",
        "/operator/sessions/{id}/no/such/page",
    ],
)
def test_an_existing_session_still_falls_back_on_a_bad_path(
    db: Session, shape: str
) -> None:
    session = _seed_session(db)
    raw = shape.format(id=session.public_id, fw=_fullwidth(session.public_id))
    assert resolve_return_to(raw, db, viewer=_owner(db, session)) == DEFAULT_TARGET


# --- Who may be told a session's name (participant audit P1) ----------------


@pytest.mark.parametrize("shape", ["/operator/sessions/{id}", "/me/sessions/{id}"])
def test_a_stranger_is_not_told_the_session_name(db: Session, shape: str) -> None:
    """The answer for a session the viewer cannot see is the one for a
    session that does not exist, so the label confirms nothing."""
    session = _seed_session(db, name="Secret Review")
    stranger = _user(db, "stranger@example.edu")
    raw = shape.format(id=session.public_id)
    assert resolve_return_to(raw, db, viewer=stranger) == PARTICIPANT_DEFAULT
    assert resolve_return_to(raw, db, viewer=None) == PARTICIPANT_DEFAULT


def test_a_sys_admin_is_told_any_session_name(db: Session) -> None:
    """Sessions Diagnostics already lists every session by name."""
    session = _seed_session(db, name="Overseen")
    admin = _user(db, "admin@example.edu", is_sys_admin=True)
    target = resolve_return_to(f"/me/sessions/{session.public_id}", db, viewer=admin)
    assert target.label == "Overseen"


@pytest.mark.parametrize("role", ["reviewer", "observer"])
def test_an_active_reviewer_or_observer_is_told_the_name(
    db: Session, role: str
) -> None:
    session = _seed_session(db, name="Mine Too")
    viewer = _user(db, "pat@example.edu")
    if role == "reviewer":
        db.add(Reviewer(session_id=session.id, name="Pat", email="PAT@example.edu"))
    else:
        db.add(Observer(session_id=session.id, display_name="Pat", email="pat@example.edu"))
    db.flush()
    target = resolve_return_to(f"/me/sessions/{session.public_id}", db, viewer=viewer)
    assert target.label == "Mine Too"


def test_an_inactive_reviewer_is_not_told_the_name(db: Session) -> None:
    session = _seed_session(db, name="Left It")
    viewer = _user(db, "pat@example.edu")
    db.add(
        Reviewer(
            session_id=session.id,
            name="Pat",
            email="pat@example.edu",
            status="inactive",
        )
    )
    db.flush()
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def test_a_role_on_another_session_does_not_name_this_one(db: Session) -> None:
    session = _seed_session(db, name="Not Yours")
    other = ReviewSession(
        name="Yours", code="rrw-other", created_by_user_id=session.created_by_user_id
    )
    db.add(other)
    db.flush()
    viewer = _user(db, "pat@example.edu")
    db.add(Reviewer(session_id=other.id, name="Pat", email="pat@example.edu"))
    db.flush()
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def test_a_reviewee_without_a_grant_is_not_told_the_name(db: Session) -> None:
    """A reviewee with nothing granted is a stranger (19F), so the back
    link must not name the session either."""
    session = _seed_session(db, name="About You")
    viewer = _user(db, "dana@example.edu")
    db.add(
        Reviewee(
            session_id=session.id, name="Dana", email_or_identifier="dana@example.edu"
        )
    )
    db.flush()
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def _grant_reviewees(db: Session, session: ReviewSession) -> None:
    """A reviewee grant that resolves now: an expired session inside its
    release window, with a reviewee after-release policy row."""
    instrument = Instrument(session_id=session.id, name="Feedback", order=1)
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            after_release_granularity="row",
            after_release_identification="identified",
        )
    )
    session.status = "expired"
    session.responses_release_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.flush()


def _second_session(db: Session, first: ReviewSession, name: str) -> ReviewSession:
    other = ReviewSession(
        name=name, code=f"rrw-{name.lower()}", created_by_user_id=first.created_by_user_id
    )
    db.add(other)
    db.flush()
    return other


def test_a_reviewee_is_told_the_name_while_a_grant_resolves(db: Session) -> None:
    """The same rule as their `/me` row: named exactly while a grant
    resolves, and not once the session goes back to draft."""
    session = _seed_session(db, name="Released")
    viewer = _user(db, "dana@example.edu")
    db.add(
        Reviewee(
            session_id=session.id, name="Dana", email_or_identifier="dana@example.edu"
        )
    )
    _grant_reviewees(db, session)
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer).label == "Released"

    session.status = "draft"
    db.flush()
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def test_a_grant_on_one_session_does_not_name_another(db: Session) -> None:
    """A reviewee on two sessions, granted on one: the other stays
    unnamed, exactly as it stays off their `/me`."""
    granted = _seed_session(db, name="Granted")
    ungranted = _second_session(db, granted, "Ungranted")
    viewer = _user(db, "dana@example.edu")
    for s in (granted, ungranted):
        db.add(
            Reviewee(
                session_id=s.id, name="Dana", email_or_identifier="dana@example.edu"
            )
        )
    _grant_reviewees(db, granted)
    assert (
        resolve_return_to(f"/me/sessions/{granted.public_id}", db, viewer=viewer).label
        == "Granted"
    )
    raw = f"/me/sessions/{ungranted.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def test_an_observer_on_another_session_is_not_told_this_name(db: Session) -> None:
    session = _seed_session(db, name="Not Observed")
    other = _second_session(db, session, "Observed")
    viewer = _user(db, "pat@example.edu")
    db.add(Observer(session_id=other.id, display_name="Pat", email="pat@example.edu"))
    db.flush()
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT


def test_a_callable_viewer_is_resolved_at_most_once_and_only_when_needed(
    db: Session,
) -> None:
    session = _seed_session(db, name="Lazy")
    calls: list[int] = []

    def viewer() -> User:
        calls.append(1)
        return _owner(db, session)

    # Allowlisted targets that name no session never ask.
    assert resolve_return_to("/me", db, viewer=viewer).label == "your reviews"
    assert resolve_return_to("/operator/settings", db, viewer=viewer).label == "Settings"
    assert calls == []
    # A session path asks once.
    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer).label == "Lazy"
    assert calls == [1]
    # A fallback asks once too: it decides between the lobby and /me.
    assert resolve_return_to(None, db, viewer=viewer) == DEFAULT_TARGET
    assert calls == [1, 1]


def test_a_refused_name_and_its_fallback_share_one_lookup(db: Session) -> None:
    """A session path the viewer may not name asks twice (may it name
    the session? then which fallback?); the lookup runs once."""
    session = _seed_session(db, name="Not Theirs")
    stranger = _user(db, "stranger@example.edu")
    calls: list[int] = []

    def viewer() -> User:
        calls.append(1)
        return stranger

    raw = f"/me/sessions/{session.public_id}"
    assert resolve_return_to(raw, db, viewer=viewer) == PARTICIPANT_DEFAULT
    assert calls == [1]
