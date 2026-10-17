"""Findings P5: a signed-in user whose email claim changes keeps their row.

``app/auth/identity.py`` now honors the stated claim priority, which can
move a user to a different email than the one their row was created
with. ``find_user`` (``users.find_signed_in_user``) matches the Entra
object id first, moving that row to the new email when no other row
holds it, then falls back to the email, recording the object id on a
row that has none.
"""

from __future__ import annotations

import pytest
from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import permissions
from app.web.deps import find_user, get_or_create_user


def _sign_in(db: Session, auth: AuthenticatedUser) -> User:
    return get_or_create_user(
        request=Request({"type": "http"}), current_user=auth, db=db
    )


def _identity(email: str, principal_id: str | None) -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id=principal_id, email=email, name="Pat", provider="aad"
    )


def _email_changes(db: Session) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "workspace.user_email_changed"
            )
        ).scalars()
    )


# --- The principal id decides first ----------------------------------------


def test_a_changed_email_keeps_the_row_flags_and_ownership(db: Session) -> None:
    pat = User(
        email="pat.old@example.edu",
        display_name="Pat",
        external_principal_id="pat-oid",
        is_operator=True,
        is_sys_admin=True,
    )
    db.add(pat)
    db.flush()
    owned = ReviewSession(name="S", code="p5-own", created_by_user_id=pat.id)
    db.add(owned)
    db.flush()
    db.add(SessionOperator(session_id=owned.id, user_id=pat.id, role="owner"))
    db.commit()

    returned = _sign_in(db, _identity(" Pat.New@example.edu ", "pat-oid"))

    assert returned.id == pat.id
    assert returned.email == "Pat.New@example.edu"
    assert returned.is_operator and returned.is_sys_admin
    assert permissions.user_can_view_session(db, returned, owned.id)
    assert db.execute(select(User.id)).scalars().all() == [pat.id]

    (event,) = _email_changes(db)
    assert event.actor_user_id is None
    assert event.detail["changes"] == {
        "email": ["pat.old@example.edu", "Pat.New@example.edu"]
    }
    assert event.detail["refs"] == {"target_user_id": pat.id}

    # The same email again, cased differently: no second rename.
    again = _sign_in(db, _identity("pat.new@example.edu", "pat-oid"))
    assert again.id == pat.id
    assert again.email == "Pat.New@example.edu"
    assert len(_email_changes(db)) == 1


def _owned_session(db: Session, owner: User, code: str) -> ReviewSession:
    rs = ReviewSession(name=code, code=code, created_by_user_id=owner.id)
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=owner.id, role="owner"))
    db.flush()
    return rs


def _absorptions(db: Session) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent).where(AuditEvent.event_type == "workspace.user_absorbed")
        ).scalars()
    )


def test_the_principal_row_absorbs_an_invite_holding_the_new_email(
    db: Session,
) -> None:
    """Codex on the rulings PR: an invite pre-seeded for the newly
    resolved address must not strand the account that owns the flags.
    It has never been signed in to, so it folds in: flags OR'd,
    memberships moved (a shared session keeps one), row gone, email
    taken."""
    original = User(
        email="sam.old@example.edu", external_principal_id="sam-oid", is_operator=True
    )
    creator = User(email="creator@example.edu")
    db.add_all([original, creator])
    db.flush()
    invite = User(email="sam.new@example.edu", is_sys_admin=True)
    db.add(invite)
    db.flush()
    mine = _owned_session(db, original, "p5-mine")
    theirs = _owned_session(db, creator, "p5-theirs")
    shared = _owned_session(db, creator, "p5-shared")
    db.add_all(
        [
            SessionOperator(session_id=theirs.id, user_id=invite.id, role="owner"),
            SessionOperator(session_id=shared.id, user_id=invite.id, role="owner"),
            SessionOperator(session_id=shared.id, user_id=original.id, role="owner"),
        ]
    )
    db.commit()
    invite_id = invite.id

    returned = _sign_in(db, _identity(" Sam.New@example.edu ", "sam-oid"))

    assert returned.id == original.id
    assert returned.email == "Sam.New@example.edu"
    assert returned.is_operator and returned.is_sys_admin
    assert db.get(User, invite_id) is None
    for rs in (mine, theirs, shared):
        assert permissions.user_can_view_session(db, returned, rs.id)
    memberships = db.execute(
        select(SessionOperator.session_id).where(
            SessionOperator.user_id == original.id
        )
    ).scalars().all()
    assert sorted(memberships) == sorted([mine.id, theirs.id, shared.id])
    assert db.execute(
        select(SessionOperator.id).where(SessionOperator.user_id == invite_id)
    ).first() is None

    (event,) = _absorptions(db)
    assert event.actor_user_id is None
    assert event.detail["changes"] == {
        "email": ["sam.old@example.edu", "Sam.New@example.edu"],
        "is_sys_admin": [False, True],
    }
    assert event.detail["refs"] == {
        "target_user_id": original.id,
        "absorbed_user_id": invite_id,
    }
    assert event.detail["context"] == {"memberships_moved": 1}
    assert _email_changes(db) == []


@pytest.mark.parametrize("history", ["own_principal", "acted", "created_session"])
def test_a_holder_that_was_signed_in_to_is_not_absorbed(
    db: Session, history: str
) -> None:
    """A row with its own principal id, or anything a sign-in leaves
    behind, is someone's account: the principal-id row stays put and
    keeps its email, and nothing is merged."""
    original = User(
        email="lee.old@example.edu", external_principal_id="lee-oid", is_operator=True
    )
    holder = User(
        email="lee.new@example.edu",
        external_principal_id="other-oid" if history == "own_principal" else None,
        is_sys_admin=True,
    )
    db.add_all([original, holder])
    db.flush()
    if history == "acted":
        db.add(AuditEvent(event_type="x.y", summary="acted", actor_user_id=holder.id))
    if history == "created_session":
        db.add(ReviewSession(name="S", code="p5-made", created_by_user_id=holder.id))
    db.commit()

    returned = _sign_in(db, _identity("lee.new@example.edu", "lee-oid"))

    assert returned.id == original.id
    assert returned.email == "lee.old@example.edu"
    assert not returned.is_sys_admin
    db.refresh(holder)
    assert holder.email == "lee.new@example.edu"
    assert _absorptions(db) == []
    assert _email_changes(db) == []


def test_the_debug_lookup_absorbs_nothing(db: Session) -> None:
    original = User(email="max.old@example.edu", external_principal_id="max-oid")
    invite = User(email="max.new@example.edu", is_operator=True)
    db.add_all([original, invite])
    db.commit()

    found = find_user(
        db, _identity("max.new@example.edu", "max-oid"), move_email=False
    )

    assert found is not None and found.id == original.id
    db.refresh(invite)
    assert invite.email == "max.new@example.edu"
    assert _absorptions(db) == []


def test_the_debug_lookup_finds_the_row_without_moving_its_email(
    db: Session,
) -> None:
    """``/auth/me/debug`` looks the viewer up with ``move_email=False``:
    the principal-id match names the viewer, and nothing is written."""
    row = User(email="dee.old@example.edu", external_principal_id="dee-oid")
    db.add(row)
    db.commit()

    found = find_user(
        db, _identity("dee.new@example.edu", "dee-oid"), move_email=False
    )

    assert found is not None and found.id == row.id
    assert found.email == "dee.old@example.edu"
    assert _email_changes(db) == []


# --- Then the email ---------------------------------------------------------


@pytest.mark.parametrize("principal_id", [None, "", "   "])
def test_no_principal_id_matches_by_email_as_before(
    db: Session, principal_id: str | None
) -> None:
    """A missing or blank principal id never matches a row — not even
    one stored blank too — and records nothing on the email match."""
    blank = User(email="blank.old@example.edu", external_principal_id=principal_id)
    by_email = User(email="eli@example.edu")
    db.add_all([blank, by_email])
    db.commit()

    assert _sign_in(db, _identity("Eli@example.edu", principal_id)).id == by_email.id
    db.refresh(by_email)
    assert by_email.external_principal_id is None

    fresh = _sign_in(db, _identity("blank.new@example.edu", principal_id))
    assert fresh.id not in (blank.id, by_email.id)
    db.refresh(blank)
    assert blank.email == "blank.old@example.edu"
    assert _email_changes(db) == []


def test_an_unknown_principal_id_and_email_creates_a_new_row(db: Session) -> None:
    old = User(email="kim.old@example.edu", external_principal_id="kim-oid")
    db.add(old)
    db.commit()

    returned = _sign_in(db, _identity("kim.new@example.edu", "someone-else"))

    assert returned.id != old.id
    assert returned.external_principal_id == "someone-else"
    assert _email_changes(db) == []


def test_an_invited_row_records_its_principal_id_on_first_sign_in(
    db: Session,
) -> None:
    """``users.invite`` stores no principal id; the first sign-in
    records it, so a later email change still finds the row."""
    invited = User(email="ivy@example.edu", is_operator=True)
    db.add(invited)
    db.commit()

    first = _sign_in(db, _identity("Ivy@example.edu", "ivy-oid"))

    assert first.id == invited.id
    assert first.external_principal_id == "ivy-oid"
    assert _email_changes(db) == []

    renamed = _sign_in(db, _identity("ivy.new@example.edu", "ivy-oid"))

    assert renamed.id == invited.id
    assert renamed.email == "ivy.new@example.edu"
    assert renamed.is_operator
    assert len(_email_changes(db)) == 1


@pytest.mark.parametrize("stored", ["", "  "])
def test_a_blank_stored_principal_id_is_recorded_over(
    db: Session, stored: str
) -> None:
    row = User(email="bea@example.edu", external_principal_id=stored)
    db.add(row)
    db.commit()

    returned = _sign_in(db, _identity("bea@example.edu", "bea-oid"))

    assert returned.external_principal_id == "bea-oid"


def test_a_differing_stored_principal_id_is_left_alone(db: Session) -> None:
    row = User(email="dan@example.edu", external_principal_id="dan-oid")
    db.add(row)
    db.commit()

    returned = _sign_in(db, _identity("dan@example.edu", "other-oid"))

    assert returned.id == row.id
    assert returned.external_principal_id == "dan-oid"


def test_the_debug_lookup_records_no_principal_id(db: Session) -> None:
    invited = User(email="deb@example.edu")
    db.add(invited)
    db.commit()

    found = find_user(db, _identity("deb@example.edu", "deb-oid"), move_email=False)

    assert found is not None and found.id == invited.id
    db.refresh(invited)
    assert invited.external_principal_id is None


# --- Fake auth ----------------------------------------------------------------


def test_a_fake_identity_never_matches_or_records_its_principal_id(
    db: Session,
) -> None:
    """``FAKE_AUTH_PRINCIPAL_ID`` is one slot every ``FAKE_AUTH_EMAIL``
    shares; switching the fake email must not rename the developer's
    row, and signing in must not record the slot."""
    dev = User(email="operator@example.edu", external_principal_id="local-dev")
    invited = User(email="op2@example.edu")
    db.add_all([dev, invited])
    db.commit()

    def fake(email: str) -> AuthenticatedUser:
        return AuthenticatedUser(
            principal_id="local-dev",
            email=email,
            name="Dev",
            provider="fake",
            is_fake=True,
        )

    assert find_user(db, fake("reviewer@example.edu")) is None
    found = find_user(db, fake("op2@example.edu"))
    assert found is not None and found.id == invited.id
    db.refresh(dev)
    db.refresh(invited)
    assert dev.email == "operator@example.edu"
    assert invited.external_principal_id is None
