"""The Owners card's save route, ``POST /sessions/{id}/owners/save``
(19S Item 10 rung C).

Session Home's Owners card stages owners as Create's does and saves them
with its own Save (author's ruling, 2026-09-23). This rung lands the
route; the card posts to it from rung D. The contract, each pinned here:

- the card posts the owners it was rendered with (``owners_original``)
  beside its table (``owners``), and **only the difference is applied**,
  to the owners the session has now: a stale page neither drops an owner
  someone else added nor restores one they removed, and only additions
  are validated, so an owner who lost operator status blocks nothing;
- the change is resolved **before** any write: a non-operator address,
  or removing every owner, lands back on the card's banner having saved
  nothing;
- any lifecycle state, as the lobby's tag edit;
- saving yourself out lands on the sessions lobby;
- one save's owner events share one correlation id.
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


def _alice(db: Session) -> User:
    return db.execute(select(User).where(User.email == CREATOR)).scalar_one()


def _owners(db: Session, review_session: ReviewSession) -> set[str]:
    db.expire_all()
    rows = db.execute(
        select(User.email)
        .join(SessionOperator, SessionOperator.user_id == User.id)
        .where(SessionOperator.session_id == review_session.id)
    ).scalars()
    return set(rows)


def _owner_events(db: Session, review_session: ReviewSession) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type.in_(
                    ["session.owner_added", "session.owner_removed"]
                ),
            )
        ).scalars()
    )


def _save(
    client: TestClient,
    review_session: ReviewSession,
    owners: list[str],
    *,
    original: list[str] | None = None,
):
    """POST the card's Save. ``original`` is what the page was rendered
    with; by default the owners the session has now, as a fresh page
    would send."""
    if original is None:
        original = sorted(_owners(object_session(review_session), review_session))
    return client.post(
        f"/operator/sessions/{review_session.id}/owners/save",
        data={"owners": owners, "owners_original": original},
        follow_redirects=False,
    )


def _home(review_session: ReviewSession, error: str | None = None) -> str:
    query = f"?owners_error={error}" if error else ""
    return f"/operator/sessions/{review_session.id}{query}#owners-card"


def test_an_addition_is_saved(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-ADD")
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, [CREATOR, "Bob@Example.edu "])

    assert response.status_code == 303
    assert response.headers["location"] == _home(review_session)
    assert _owners(db, review_session) == {CREATOR, "bob@example.edu"}


def test_a_removal_is_saved(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-RM")
    bob = _operator(db, "bob@example.edu")
    session_owners.add_owner(
        db, review_session=review_session, actor=_alice(db), target=bob
    )

    response = _save(client, review_session, [CREATOR])

    assert response.headers["location"] == _home(review_session)
    assert _owners(db, review_session) == {CREATOR}


def test_an_address_typed_and_never_added_is_saved(
    client: TestClient, db: Session
) -> None:
    """Without JavaScript the picker's box posts as one more ``owners``
    value beside the rows, so the no-JS path adds one owner."""
    review_session = _create(client, db, "OWN-NOJS")
    _operator(db, "bob@example.edu")

    _save(client, review_session, [CREATOR, "bob@example.edu", ""])

    assert _owners(db, review_session) == {CREATOR, "bob@example.edu"}


def test_a_non_operator_lands_on_the_banner_and_saves_nothing(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-NOTOP")
    _operator(db, "bob@example.edu")
    _operator(db, "eve@example.edu", is_operator=False)

    response = _save(
        client, review_session, ["bob@example.edu", "eve@example.edu"]
    )

    assert response.headers["location"] == _home(review_session, "not_in_workspace")
    assert _owners(db, review_session) == {CREATOR}, "neither the add nor the remove"
    assert _owner_events(db, review_session) == []


def test_removing_every_owner_lands_on_the_banner_and_saves_nothing(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-EMPTY")

    response = _save(client, review_session, [])

    assert response.headers["location"] == _home(review_session, "last_owner")
    assert _owners(db, review_session) == {CREATOR}
    body = client.get(response.headers["location"]).text
    assert "A session always keeps at least one owner." in body


def test_an_activated_session_saves_too(client: TestClient, db: Session) -> None:
    """Any lifecycle state, as the lobby's tags (author's ruling)."""
    review_session = _create(client, db, "OWN-READY")
    review_session.status = "ready"
    db.commit()
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, [CREATOR, "bob@example.edu"])

    assert response.headers["location"] == _home(review_session)
    assert _owners(db, review_session) == {CREATOR, "bob@example.edu"}


def test_saving_yourself_out_lands_on_the_lobby(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-SELF")
    _operator(db, "bob@example.edu")

    response = _save(client, review_session, ["bob@example.edu"])

    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sessions"
    assert _owners(db, review_session) == {"bob@example.edu"}


def test_one_save_is_one_correlation_id(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CORR")
    bob = _operator(db, "bob@example.edu")
    _operator(db, "carol@example.edu")
    session_owners.add_owner(
        db, review_session=review_session, actor=_alice(db), target=bob
    )
    before = {e.id for e in _owner_events(db, review_session)}

    _save(client, review_session, [CREATOR, "carol@example.edu"])

    events = [e for e in _owner_events(db, review_session) if e.id not in before]
    assert {e.event_type for e in events} == {
        "session.owner_added",
        "session.owner_removed",
    }
    assert len({e.correlation_id for e in events}) == 1


def test_an_unchanged_table_emits_no_owner_events(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-SAME")

    response = _save(client, review_session, [CREATOR])

    assert response.headers["location"] == _home(review_session)
    assert _owner_events(db, review_session) == []


def test_a_stale_page_does_not_drop_an_owner_added_elsewhere(
    client: TestClient, db: Session
) -> None:
    """The page was rendered with alice and bob; bob then added carol from
    another tab. Alice's save, adding dave, must not remove carol."""
    review_session = _create(client, db, "OWN-STALE-ADD")
    bob = _operator(db, "bob@example.edu")
    carol = _operator(db, "carol@example.edu")
    _operator(db, "dave@example.edu")
    session_owners.add_owner(
        db, review_session=review_session, actor=_alice(db), target=bob
    )
    rendered = [CREATOR, "bob@example.edu"]
    session_owners.add_owner(
        db, review_session=review_session, actor=bob, target=carol
    )

    _save(
        client,
        review_session,
        [*rendered, "dave@example.edu"],
        original=rendered,
    )

    assert _owners(db, review_session) == {
        CREATOR,
        "bob@example.edu",
        "carol@example.edu",
        "dave@example.edu",
    }


def test_a_stale_page_does_not_restore_an_owner_removed_elsewhere(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-STALE-RM")
    bob = _operator(db, "bob@example.edu")
    alice = _alice(db)
    session_owners.add_owner(db, review_session=review_session, actor=alice, target=bob)
    rendered = [CREATOR, "bob@example.edu"]
    session_owners.remove_owner(
        db, review_session=review_session, actor=alice, target=bob
    )

    _save(client, review_session, rendered, original=rendered)

    assert _owners(db, review_session) == {CREATOR}


def test_an_owner_who_lost_operator_status_does_not_block_the_save(
    client: TestClient, db: Session
) -> None:
    """Only additions are validated. A demoted owner still in the table
    must not turn every save into a refusal."""
    review_session = _create(client, db, "OWN-DEMOTED")
    bob = _operator(db, "bob@example.edu")
    _operator(db, "carol@example.edu")
    session_owners.add_owner(
        db, review_session=review_session, actor=_alice(db), target=bob
    )
    bob.is_operator = False
    db.commit()

    response = _save(
        client, review_session, [CREATOR, "bob@example.edu", "carol@example.edu"]
    )

    assert response.headers["location"] == _home(review_session)
    assert _owners(db, review_session) == {
        CREATOR,
        "bob@example.edu",
        "carol@example.edu",
    }


def test_a_refusal_during_the_write_lands_on_the_banner(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """Another save can change the owners between the resolve and the
    write, and ``set_owners`` then refuses. The card's banner says so
    rather than the request failing with a 500."""
    review_session = _create(client, db, "OWN-RACE")
    _operator(db, "bob@example.edu")

    def refuse(*args, **kwargs):
        raise session_owners.OwnerOperationError(
            code="already_owner", message="bob@example.edu is already an owner."
        )

    monkeypatch.setattr(session_owners, "set_owners", refuse)
    response = _save(client, review_session, [CREATOR, "bob@example.edu"])

    assert response.headers["location"] == _home(review_session, "already_owner")


def test_a_refusal_after_removing_yourself_lands_on_the_lobby(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """``set_owners`` commits each change as it goes, so a refusal
    part-way can follow your own removal. Session Home is then a 404 for
    you, so the lobby, not the banner (cold read, 2026-09-23)."""
    review_session = _create(client, db, "OWN-RACE-SELF")
    bob = _operator(db, "bob@example.edu")
    alice = _alice(db)
    real_set_owners = session_owners.set_owners

    def remove_self_then_refuse(db_, *, review_session, actor, targets, correlation_id):
        real_set_owners(
            db_,
            review_session=review_session,
            actor=actor,
            targets=[bob],
            correlation_id=correlation_id,
        )
        raise session_owners.OwnerOperationError(
            code="already_owner", message="carol@example.edu is already an owner."
        )

    monkeypatch.setattr(session_owners, "set_owners", remove_self_then_refuse)
    response = _save(client, review_session, ["bob@example.edu"])

    assert response.headers["location"] == "/operator/sessions"
    assert alice.email not in _owners(db, review_session)


def test_a_non_owner_is_refused(
    client: TestClient, db: Session, make_client, bob
) -> None:
    review_session = _create(client, db, "OWN-OUTSIDER")
    bob_client = make_client(bob)

    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/owners/save",
        data={"owners": [CREATOR, "bob@example.edu"], "owners_original": [CREATOR]},
        follow_redirects=False,
    )

    assert response.status_code in (403, 404)
    assert _owners(db, review_session) == {CREATOR}


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
