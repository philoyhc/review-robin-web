"""19S Item 9 rung 4 — ``session_owners.resolve_owners`` and ``set_owners``.

The Owners card on Create stages rows and saves them with the page, and
Item 10 will do the same on Session Home. Both need the whole owner list
validated before anything is written, and a replace that never lets the
session pass through zero owners.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import session_owners


def _user(db: Session, email: str, *, is_operator: bool = True) -> User:
    user = User(email=email, is_operator=is_operator)
    db.add(user)
    db.flush()
    return user


def _owned_session(db: Session, owner: User, code: str) -> ReviewSession:
    review_session = ReviewSession(
        name=code, code=code, created_by_user_id=owner.id
    )
    db.add(review_session)
    db.flush()
    db.add(
        SessionOperator(session_id=review_session.id, user_id=owner.id, role="owner")
    )
    db.flush()
    return review_session


def _owner_emails(db: Session, review_session: ReviewSession) -> list[str]:
    return sorted(row.email for row in session_owners.list_owners(db, review_session))


def _owner_events(db: Session, review_session: ReviewSession) -> list[str]:
    return [
        e.event_type
        for e in db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type.in_(
                    ["session.owner_added", "session.owner_removed"]
                ),
            )
        ).scalars()
    ]


# --- resolve_owners -------------------------------------------------------


def test_resolve_skips_blanks_folds_case_and_collapses_duplicates(
    db: Session,
) -> None:
    a = _user(db, "a@example.edu")
    b = _user(db, "b@example.edu")
    resolved = session_owners.resolve_owners(
        db, ["", "  ", "B@Example.edu", "a@example.edu", "b@example.edu"]
    )
    assert [u.id for u in resolved] == [b.id, a.id], "order kept, dupes gone"


@pytest.mark.parametrize("known", [True, False], ids=["non-operator", "unknown"])
def test_resolve_refuses_anyone_add_owner_would_refuse(
    db: Session, known: bool
) -> None:
    _user(db, "ok@example.edu")
    if known:
        _user(db, "outsider@example.edu", is_operator=False)
    with pytest.raises(session_owners.OwnerOperationError) as exc:
        session_owners.resolve_owners(
            db, ["ok@example.edu", "outsider@example.edu"]
        )
    assert exc.value.code == "not_in_workspace"
    assert "outsider@example.edu" in exc.value.message


# --- set_owners -----------------------------------------------------------


def test_set_owners_replaces_the_set(db: Session) -> None:
    a = _user(db, "a@example.edu")
    b = _user(db, "b@example.edu")
    c = _user(db, "c@example.edu")
    review_session = _owned_session(db, a, "SET-REPLACE")
    session_owners.add_owner(db, review_session=review_session, actor=a, target=b)

    added, removed = session_owners.set_owners(
        db, review_session=review_session, actor=a, targets=[a, c]
    )
    assert [u.id for u in added] == [c.id]
    assert [u.id for u in removed] == [b.id]
    assert _owner_emails(db, review_session) == ["a@example.edu", "c@example.edu"]


def test_set_owners_can_hand_a_session_to_someone_else(db: Session) -> None:
    """The sole owner replaced by another in one call. Only works because
    ``set_owners`` adds before it removes — the other way round, removing
    the only owner first trips ``remove_owner``'s last-owner guard."""
    a = _user(db, "a@example.edu")
    b = _user(db, "b@example.edu")
    review_session = _owned_session(db, a, "SET-HANDOVER")

    session_owners.set_owners(
        db, review_session=review_session, actor=a, targets=[b]
    )
    assert _owner_emails(db, review_session) == ["b@example.edu"]


def test_an_unchanged_set_writes_and_emits_nothing(db: Session) -> None:
    a = _user(db, "a@example.edu")
    review_session = _owned_session(db, a, "SET-SAME")

    added, removed = session_owners.set_owners(
        db, review_session=review_session, actor=a, targets=[a]
    )
    assert (added, removed) == ([], [])
    assert _owner_events(db, review_session) == []


def test_an_empty_set_is_refused_before_anything_is_removed(db: Session) -> None:
    """Two owners, on purpose. With one, ``remove_owner``'s own last-owner
    guard raises the same error and the test passes without this guard —
    the mutation run found exactly that. With two, an unguarded empty set
    removes the first owner and only then trips on the second: a partial
    write this guard exists to prevent."""
    a = _user(db, "a@example.edu")
    b = _user(db, "b@example.edu")
    review_session = _owned_session(db, a, "SET-EMPTY")
    session_owners.add_owner(db, review_session=review_session, actor=a, target=b)

    with pytest.raises(session_owners.OwnerOperationError) as exc:
        session_owners.set_owners(
            db, review_session=review_session, actor=a, targets=[]
        )
    assert exc.value.code == "last_owner"
    assert _owner_emails(db, review_session) == ["a@example.edu", "b@example.edu"]


def test_a_target_listed_twice_is_added_once(db: Session) -> None:
    """``current`` is read once, so an unowned target listed twice would
    be added twice — the second ``add_owner`` raising ``already_owner``
    after the first had committed."""
    a = _user(db, "a@example.edu")
    b = _user(db, "b@example.edu")
    review_session = _owned_session(db, a, "SET-DUP")

    added, _ = session_owners.set_owners(
        db, review_session=review_session, actor=a, targets=[a, b, b]
    )
    assert [u.id for u in added] == [b.id]
    assert _owner_emails(db, review_session) == ["a@example.edu", "b@example.edu"]
