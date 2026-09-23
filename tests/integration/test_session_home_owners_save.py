"""19S Item 10 rung 1 — the details card's Save carries the owner set.

Session Home's Owners card will stage owners the way Create's does and
save them with the card (author's ruling, 2026-09-23). This rung lands
the save path only; the page does not post ``owners`` yet, so the old
per-row forms keep working until rung 2.

The contract, each pinned below through the route:

- the card posts the set it was rendered with (``owners_original``)
  beside its table (``owners``), behind an ``owners_present`` marker;
  only a request carrying the marker touches owners, since FastAPI
  cannot tell an absent list from an empty one;
- **only the difference is applied**, to the owners the session has
  now: a stale page neither drops an owner someone else added nor
  restores one they removed (cold read F1), and only additions are
  validated, so an owner who lost operator status blocks nothing (F2);
- the set is resolved **before** any write: a non-operator address, or
  an empty set, is a 422 that saves nothing else either — the card's
  other errors are 422s too;
- outside draft and validated the Save answers 409, as for every field;
- saving yourself out lands on the sessions lobby;
- the save's owner events share its one correlation id.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import session_owners

CREATOR = "alice@example.edu"


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Owned", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _operator(db: Session, email: str, *, is_operator: bool = True) -> User:
    user = User(email=email, is_operator=is_operator)
    db.add(user)
    db.commit()
    return user


def _owners(db: Session, review_session: ReviewSession) -> set[str]:
    rows = db.execute(
        select(User.email)
        .join(SessionOperator, SessionOperator.user_id == User.id)
        .where(SessionOperator.session_id == review_session.id)
    ).scalars()
    return set(rows)


def _save(
    client: TestClient,
    review_session: ReviewSession,
    *,
    owners: list[str] | None = None,
    original: list[str] | None = None,
    marker: bool = True,
    name: str = "Renamed",
):
    """POST the details card's Save, renaming the session in the same
    request as the control: a refused save must leave the name alone
    too, or "owners unchanged" could pass for the wrong reason.

    ``original`` is what the page was rendered with; by default the
    owners the session has at the moment of the call, as a fresh page
    would send."""
    data: dict[str, object] = {
        "name": name,
        "code": review_session.code,
        "description": "",
        "display_timezone": "",
    }
    if owners is not None:
        data["owners"] = owners
        data["owners_original"] = (
            original if original is not None
            else sorted(_owners(object_session(review_session), review_session))
        )
    if marker:
        data["owners_present"] = "1"
    return client.post(
        f"/operator/sessions/{review_session.id}/config",
        data=data,
        follow_redirects=False,
    )


def _name(db: Session, review_session: ReviewSession) -> str:
    db.expire_all()
    return db.get(ReviewSession, review_session.id).name


def test_the_save_replaces_the_owner_set(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-SET")
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, owners=[CREATOR, "Bob@Example.edu"])

    assert response.status_code == 303
    assert response.headers["location"].endswith("#session-config")
    assert _owners(db, review_session) == {CREATOR, "bob@example.edu"}
    assert _name(db, review_session) == "Renamed"


def test_a_staged_removal_is_saved(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-RM")
    _operator(db, "bob@example.edu")
    _save(client, review_session, owners=[CREATOR, "bob@example.edu"])

    _save(client, review_session, owners=[CREATOR])

    assert _owners(db, review_session) == {CREATOR}


def test_without_the_marker_owners_are_left_alone(
    client: TestClient, db: Session
) -> None:
    """A page rendered before the card posted owners — a tab left open
    across the deploy — must not read as *remove every owner*."""
    review_session = _create(client, db, "OWN-NOMARK")
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, owners=["bob@example.edu"], marker=False)

    assert response.status_code == 303
    assert _name(db, review_session) == "Renamed", "the save itself went through"
    assert _owners(db, review_session) == {CREATOR}


def test_a_non_operator_is_a_422_that_saves_nothing(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-NONOP")
    _operator(db, "bob@example.edu")
    _operator(db, "carol@example.edu", is_operator=False)

    response = _save(
        client, review_session, owners=[CREATOR, "bob@example.edu", "carol@example.edu"]
    )

    assert response.status_code == 422
    assert "carol@example.edu" in response.text
    assert _name(db, review_session) == "Owned", "the rename did not land either"
    assert _owners(db, review_session) == {CREATOR}, "nor did bob"


def test_an_empty_set_is_a_422_that_saves_nothing(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-EMPTY")

    response = _save(client, review_session, owners=[])

    assert response.status_code == 422
    assert _name(db, review_session) == "Owned"
    assert _owners(db, review_session) == {CREATOR}


def test_outside_draft_and_validated_the_save_is_a_409(
    client: TestClient, db: Session
) -> None:
    """The owners follow the card's Lock / Unlock window, not their own."""
    review_session = _create(client, db, "OWN-LOCKED")
    _operator(db, "bob@example.edu")
    review_session.status = "ready"
    db.commit()

    response = _save(client, review_session, owners=[CREATOR, "bob@example.edu"])

    assert response.status_code == 409
    assert _owners(db, review_session) == {CREATOR}


def test_a_locked_session_answers_409_before_any_owner_422(
    client: TestClient, db: Session
) -> None:
    """The editable check runs before the owners are resolved, so a
    locked session reports what the rest of the card reports."""
    review_session = _create(client, db, "OWN-LOCK422")
    _operator(db, "carol@example.edu", is_operator=False)
    review_session.status = "ready"
    db.commit()

    response = _save(client, review_session, owners=["carol@example.edu"])

    assert response.status_code == 409


def test_saving_yourself_out_lands_on_the_lobby(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-SELF")
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, owners=["bob@example.edu"])

    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sessions"
    assert _owners(db, review_session) == {"bob@example.edu"}


def test_one_save_is_one_correlation_id(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CORR")
    _operator(db, "bob@example.edu")
    before = {
        e.id
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == review_session.id)
        ).scalars()
    }

    _save(client, review_session, owners=[CREATOR, "bob@example.edu"])

    events = [
        e
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == review_session.id)
        ).scalars()
        if e.id not in before
    ]
    types = {e.event_type for e in events}
    assert "session.owner_added" in types
    assert len(types) > 1, "the rename emitted a config event beside it"
    assert len({e.correlation_id for e in events}) == 1


def test_an_unchanged_set_emits_no_owner_events(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-SAME")

    _save(client, review_session, owners=[CREATOR])

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type.in_(
                ["session.owner_added", "session.owner_removed"]
            ),
        )
    ).scalars().all()
    assert events == []


def test_a_concurrent_owner_change_is_a_409_not_a_500(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """``set_owners`` runs after the config apply, so if another save
    changed the owners in between it refuses late. The route says what
    happened rather than failing with a 500."""
    review_session = _create(client, db, "OWN-RACE")
    _operator(db, "bob@example.edu")

    def refuse(*args, **kwargs):
        raise session_owners.OwnerOperationError(
            code="already_owner", message="bob@example.edu is already an owner."
        )

    monkeypatch.setattr(session_owners, "set_owners", refuse)
    response = _save(client, review_session, owners=[CREATOR, "bob@example.edu"])

    assert response.status_code == 409
    assert "Reload the page" in response.text


def test_a_stale_page_does_not_drop_an_owner_added_elsewhere(
    client: TestClient, db: Session
) -> None:
    """Cold read F1: the page was rendered with alice and bob; bob then
    added carol from another tab. Alice's save of a description change
    must not remove carol."""
    review_session = _create(client, db, "OWN-STALE-ADD")
    bob = _operator(db, "bob@example.edu")
    carol = _operator(db, "carol@example.edu")
    alice = db.execute(select(User).where(User.email == CREATOR)).scalar_one()
    session_owners.add_owner(db, review_session=review_session, actor=alice, target=bob)
    rendered = [CREATOR, "bob@example.edu"]
    session_owners.add_owner(db, review_session=review_session, actor=bob, target=carol)

    response = _save(client, review_session, owners=rendered, original=rendered)

    assert response.status_code == 303
    assert _owners(db, review_session) == {CREATOR, "bob@example.edu", "carol@example.edu"}


def test_a_stale_page_does_not_restore_an_owner_removed_elsewhere(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-STALE-RM")
    bob = _operator(db, "bob@example.edu")
    alice = db.execute(select(User).where(User.email == CREATOR)).scalar_one()
    session_owners.add_owner(db, review_session=review_session, actor=alice, target=bob)
    rendered = [CREATOR, "bob@example.edu"]
    session_owners.remove_owner(db, review_session=review_session, actor=alice, target=bob)

    _save(client, review_session, owners=rendered, original=rendered)

    assert _owners(db, review_session) == {CREATOR}


def test_an_owner_who_lost_operator_status_does_not_block_the_save(
    client: TestClient, db: Session
) -> None:
    """Cold read F2: only additions are validated. A demoted owner still
    in the table must not turn every save into a 422."""
    review_session = _create(client, db, "OWN-DEMOTED")
    bob = _operator(db, "bob@example.edu")
    alice = db.execute(select(User).where(User.email == CREATOR)).scalar_one()
    session_owners.add_owner(db, review_session=review_session, actor=alice, target=bob)
    bob.is_operator = False
    db.commit()

    response = _save(client, review_session, owners=[CREATOR, "bob@example.edu"])

    assert response.status_code == 303
    assert _name(db, review_session) == "Renamed"
    assert _owners(db, review_session) == {CREATOR, "bob@example.edu"}


def test_resolve_owner_changes_refuses_to_remove_every_owner(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-ALLGONE")
    try:
        session_owners.resolve_owner_changes(
            db, review_session, original=[CREATOR], wanted=["", "  "]
        )
    except session_owners.OwnerOperationError as exc:
        assert exc.code == "last_owner"
    else:
        raise AssertionError("removing every owner must be refused")
