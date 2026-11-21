"""Segment AD2A, rung 3: people bound by tenant and object ID (ruling 73),
the people search (ruling 75), the allowlist and an exercise's Owner and
operators (rulings 73 and 75), each change audited (ruling 74)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import audit, db, directory, operators, people
from applydesk.models import AuditEvent, ExerciseOperator, Person
from applydesk.operators import Actor, Refused
from cordware.graph import DirectoryUser, FakeDirectory, GraphError
from cordware.identity import Identity

TENANT = "tenant-1"


@pytest.fixture
def session(applydesk_db: None) -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _identity(oid: str, mail: str, upn: str | None = None, name: str = "Ana Lim") -> Identity:
    return Identity(
        principal_id=oid, email=mail, name=name, tenant_id=TENANT, upn=upn or mail, mail=mail
    )


def _events(session: Session, kind: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == kind)
        )
        or 0
    )


def _operator(session: Session, oid: str, mail: str) -> Person:
    person = people.resolve(session, _identity(oid, mail))
    assert person is not None
    person.may_operate = True
    session.flush()
    return person


SUPER = Actor(person=None, is_super_admin=True)


# --------------------------------------------------------------------------- #
# Binding
# --------------------------------------------------------------------------- #


def test_a_first_sign_in_makes_a_bound_person_and_a_second_finds_it(session: Session) -> None:
    first = people.resolve(session, _identity("o1", "ana@example.edu"))
    again = people.resolve(session, _identity("o1", "Ana.New@example.edu"))
    assert first is not None and again is not None and first.id == again.id
    assert (first.tenant_id, first.object_id) == (TENANT, "o1")
    assert _events(session, "person.created") == 1


def test_a_pending_person_is_bound_at_sign_in_by_upn_then_mail(session: Session) -> None:
    by_upn = people.pending(session, "A0001@u.example.edu", actor=None)
    by_mail = people.pending(session, "Ben@Example.edu", actor=None)
    a = people.resolve(session, _identity("o1", "ana@example.edu", upn="a0001@u.example.edu"))
    b = people.resolve(session, _identity("o2", "ben@example.edu", upn="b0002@u.example.edu"))
    assert a is not None and a.id == by_upn.id and a.bound
    assert b is not None and b.id == by_mail.id and b.object_id == "o2"
    assert _events(session, "person.bound") == 2


def test_after_binding_the_address_matches_nothing(session: Session) -> None:
    """Once bound, email is a snapshot: another account with that address
    gets its own person."""
    people.resolve(session, _identity("o1", "ana@example.edu"))
    other = people.resolve(session, _identity("o9", "ana@example.edu"))
    assert other is not None and other.object_id == "o9"
    assert session.scalar(select(func.count()).select_from(Person)) == 2


def test_an_identity_with_no_tenant_or_object_id_is_not_bound(session: Session) -> None:
    assert people.resolve(session, Identity(principal_id=None, email="x@e.edu", name=None)) is None


def test_a_directory_find_is_stored_bound(session: Session) -> None:
    pending = people.pending(session, "cy@example.edu", actor=None)
    user = DirectoryUser(
        id="o3", display_name="Cy Ong", mail="cy@example.edu", user_principal_name="cy@u.edu"
    )
    person = people.from_directory(session, user, TENANT, actor=None)
    assert person.id == pending.id and person.bound and person.display_name == "Cy Ong"
    assert people.from_directory(session, user, TENANT, actor=None).id == person.id


def test_a_directory_find_is_audited_to_the_searcher_not_the_found(session: Session) -> None:
    """Codex on #4110: the person found did nothing; the searcher did, or
    no one on record (the super-admin with no row)."""
    searcher = people.resolve(session, _identity("o1", "ann@example.edu"))
    assert searcher is not None
    found = DirectoryUser(
        id="o4", display_name="Di Lim", mail="di@example.edu", user_principal_name="di@u.edu"
    )
    pending = people.pending(session, "ed@example.edu", actor=searcher)
    bound = DirectoryUser(
        id="o5", display_name="Ed Ho", mail="ed@example.edu", user_principal_name="ed@u.edu"
    )
    made = people.from_directory(session, found, TENANT, actor=searcher)
    people.from_directory(session, bound, TENANT, actor=None)
    events = {
        (e.event_type, e.detail["context"]["how"]): e.actor_id
        for e in session.scalars(select(AuditEvent))
        if e.detail.get("context", {}).get("how") == "directory"
    }
    assert events == {
        ("person.created", "directory"): searcher.id,
        ("person.bound", "directory"): None,
    }
    assert made.id != searcher.id and pending.bound


# --------------------------------------------------------------------------- #
# The people search
# --------------------------------------------------------------------------- #


def test_the_search_shows_people_on_record_first_then_the_directory(session: Session) -> None:
    fake = FakeDirectory()
    found = directory.search(session, "a", fake)
    assert found == directory.SearchResult((), ())  # too short
    someone = fake.search_users("jane")[0]
    people.from_directory(session, someone, TENANT, actor=None)
    result = directory.search(session, someone.display_name[:4], fake)
    assert [p.object_id for p in result.on_record] == [someone.id]
    assert someone.id not in {u.id for u in result.in_directory}  # not twice


def test_a_failed_directory_search_says_so_and_adds_no_one(session: Session) -> None:
    class Down:
        def find_users(self, address: str) -> list[DirectoryUser]:
            raise GraphError("server", 503)

        def search_users(self, prefix: str) -> list[DirectoryUser]:
            raise GraphError("server", 503)

    people.pending(session, "dee@example.edu", actor=None)
    result = directory.search(session, "dee", Down())
    assert result.directory_failed == "server" and len(result.on_record) == 1
    assert result.in_directory == ()


def test_the_allowlist_search_finds_only_the_allowlist(session: Session) -> None:
    allowed = _operator(session, "o1", "ana@example.edu")
    people.resolve(session, _identity("o2", "anna@example.edu", name="Anna Tan"))
    result = directory.search(session, "ann", FakeDirectory(), allowlist_only=True)
    assert result.on_record == () and result.in_directory == ()
    result = directory.search(session, "ana@", FakeDirectory(), allowlist_only=True)
    assert [p.id for p in result.on_record] == [allowed.id]


# --------------------------------------------------------------------------- #
# The allowlist and an exercise's operators
# --------------------------------------------------------------------------- #


def test_only_the_super_admin_admits_and_revokes(session: Session) -> None:
    owner = _operator(session, "o1", "ana@example.edu")
    other = people.pending(session, "ben@example.edu", actor=None)
    with pytest.raises(Refused):
        operators.admit(session, Actor(owner), other)
    operators.admit(session, SUPER, other)
    assert operators.may_operate(other)
    with pytest.raises(Refused):
        operators.admit(session, SUPER, other)
    operators.revoke(session, SUPER, other)
    assert not operators.may_operate(other) and other.revoked_at is not None
    assert (_events(session, "person.admitted"), _events(session, "person.revoked")) == (1, 1)


def test_making_an_exercise_makes_its_owner(session: Session) -> None:
    owner = _operator(session, "o1", "ana@example.edu")
    stranger = people.resolve(session, _identity("o2", "ben@example.edu"))
    with pytest.raises(Refused):
        operators.create_exercise(session, Actor(stranger), "abcdefghjk")
    exercise = operators.create_exercise(session, Actor(owner), "abcdefghjk")
    assert operators.owner_of(session, exercise) is owner
    assert operators.can_operate(session, exercise, Actor(owner))
    assert not operators.can_operate(session, exercise, Actor(stranger))
    assert operators.can_operate(session, exercise, SUPER)


def test_the_owner_adds_removes_and_hands_over(session: Session) -> None:
    owner = _operator(session, "o1", "ana@example.edu")
    colleague = _operator(session, "o2", "ben@example.edu")
    outsider = people.resolve(session, _identity("o3", "cy@example.edu"))
    assert outsider is not None
    exercise = operators.create_exercise(session, Actor(owner), "abcdefghjk")
    with pytest.raises(Refused, match="operator list"):
        operators.add_operator(session, exercise, Actor(owner), outsider)
    operators.add_operator(session, exercise, Actor(owner), colleague)
    with pytest.raises(Refused, match="Already"):
        operators.add_operator(session, exercise, Actor(owner), colleague)
    with pytest.raises(Refused, match="Owner adds"):
        operators.add_operator(session, exercise, Actor(colleague), outsider)
    with pytest.raises(Refused, match="cannot be removed"):
        operators.remove_operator(session, exercise, Actor(owner), owner)
    operators.hand_over(session, exercise, Actor(owner), colleague)
    assert operators.owner_of(session, exercise) is colleague
    assert [(p.id, o) for p, o in operators.current_operators(session, exercise)] == [
        (colleague.id, True),
        (owner.id, False),
    ]
    operators.remove_operator(session, exercise, Actor(colleague), owner)
    assert not operators.can_operate(session, exercise, Actor(owner))
    operators.add_operator(session, exercise, Actor(colleague), owner)  # re-added
    assert operators.can_operate(session, exercise, Actor(owner))
    owners = session.scalar(
        select(func.count()).where(
            ExerciseOperator.exercise_id == exercise.id,
            ExerciseOperator.is_owner.is_(True),
            ExerciseOperator.removed_at.is_(None),
        )
    )
    assert owners == 1


def test_revoking_ends_access_but_keeps_the_grant(session: Session) -> None:
    owner = _operator(session, "o1", "ana@example.edu")
    colleague = _operator(session, "o2", "ben@example.edu")
    exercise = operators.create_exercise(session, Actor(owner), "abcdefghjk")
    operators.add_operator(session, exercise, Actor(owner), colleague)
    operators.revoke(session, SUPER, colleague)
    assert not operators.can_operate(session, exercise, Actor(colleague))
    assert operators.operated_exercises(session, Actor(colleague)) == []
    operators.admit(session, SUPER, colleague)
    assert operators.operated_exercises(session, Actor(colleague)) == [exercise]
    # A revoked Owner keeps the row; the super-admin hands it over.
    operators.revoke(session, SUPER, owner)
    with pytest.raises(Refused):
        operators.add_operator(session, exercise, Actor(owner), colleague)
    operators.hand_over(session, exercise, SUPER, colleague)
    assert operators.owner_of(session, exercise) is colleague


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #


def test_every_emitted_event_type_is_registered() -> None:
    import re
    from pathlib import Path

    root = Path(audit.__file__).parent
    emitted = {
        match
        for path in root.glob("*.py")
        for match in re.findall(r'event_type="([a-z_.]+)"', path.read_text(encoding="utf-8"))
    }
    assert emitted == set(audit.EVENT_SCHEMAS)


def test_a_detail_off_its_schema_fails_in_tests(session: Session) -> None:
    with pytest.raises(audit.AuditDetailValidationError):
        audit.write_event(session, event_type="person.admitted", actor=None, reason="not allowed")
    with pytest.raises(audit.AuditDetailValidationError):
        audit.write_event(session, event_type="no.such", actor=None)
    with pytest.raises(audit.AuditDetailValidationError):
        audit.write_event(session, event_type="person.admitted", actor=None, refs={"person": 1})


def test_an_address_only_reuses_a_pending_person_never_a_bound_one(session: Session) -> None:
    """Codex on #4110: a bound person's email is a snapshot, never matched."""
    bound = people.resolve(session, _identity("o1", "ana@example.edu"))
    assert bound is not None
    made = people.pending(session, "ANA@example.edu", actor=None)
    assert made.id != bound.id and not made.bound
    assert people.pending(session, "ana@example.edu", actor=None).id == made.id


def test_the_database_holds_one_owner_per_exercise(session: Session) -> None:
    """Codex on #4110: two handovers at once must not leave two Owners; the
    partial unique index refuses the second Owner row."""
    from sqlalchemy.exc import IntegrityError

    owner = _operator(session, "o1", "ana@example.edu")
    colleague = _operator(session, "o2", "ben@example.edu")
    exercise = operators.create_exercise(session, Actor(owner), "abcdefghjk")
    operators.add_operator(session, exercise, Actor(owner), colleague)
    session.commit()
    grant = session.scalar(
        select(ExerciseOperator).where(ExerciseOperator.person_id == colleague.id)
    )
    assert grant is not None
    grant.is_owner = True  # as a racing handover would, without clearing the Owner
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
    operators.hand_over(session, exercise, Actor(owner), colleague)  # the service's order holds
    session.commit()
    assert operators.owner_of(session, exercise) == colleague


def test_a_reassigned_address_s_new_account_still_shows_in_the_search(session: Session) -> None:
    """Codex on #4110: a bound person matches a directory account by object
    ID only, so a new account with the old address is not hidden."""

    class Reassigned:
        def search_users(self, query: str) -> list[DirectoryUser]:
            return [
                DirectoryUser(
                    id="new",
                    display_name="Ana Lim",
                    mail="ana@example.edu",
                    user_principal_name="ana@u.edu",
                )
            ]

    old = people.resolve(session, _identity("old", "ana@example.edu"))
    assert old is not None
    result = directory.search(session, "ana", Reassigned())  # pyright: ignore[reportArgumentType]  -- a stub directory
    assert [p.id for p in result.on_record] == [old.id]
    assert [u.id for u in result.in_directory] == ["new"]


def test_creation_and_binding_events_name_the_person(session: Session) -> None:
    """Codex on #4110: each person.created / person.bound carries refs.person_id."""
    pending = people.pending(session, "ed@example.edu", actor=None)
    bound = people.resolve(session, _identity("o9", "ed@example.edu"))
    fresh = people.resolve(session, _identity("o8", "fi@example.edu"))
    assert bound is not None and fresh is not None
    rows = [
        (e.event_type, e.detail["refs"]["person_id"])
        for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id))
    ]
    assert rows == [
        ("person.created", pending.id),
        ("person.bound", pending.id),
        ("person.created", fresh.id),
    ]


def test_a_pending_person_bound_by_another_request_is_not_taken_over(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #4110: two accounts sharing an address resolve at once. This
    request read the pending row, then another bound it and committed; this
    request's bind must not overwrite that, and it gets a person of its own."""
    pending = people.pending(session, "ana@example.edu", actor=None)
    operators.admit(session, SUPER, pending)
    session.commit()
    stale = session.get(Person, pending.id)  # what this request read
    assert stale is not None and not stale.bound

    other = db.new_session()  # the other request, first to bind it
    first = people.resolve(other, _identity("o1", "ana@example.edu"))
    other.commit()
    other.close()
    assert first is not None and first.id == pending.id

    looks = iter([stale])
    real = people._pending_person  # pyright: ignore[reportPrivateUsage]  -- replay the stale read

    def stale_once(s: Session, *keys: str | None) -> Person | None:
        return next(looks, None) or real(s, *keys)

    monkeypatch.setattr(people, "_pending_person", stale_once)
    second = people.resolve(session, _identity("o2", "ana@example.edu"))
    session.commit()
    assert second is not None and second.id != pending.id and second.object_id == "o2"
    session.refresh(stale)
    assert stale.object_id == "o1" and stale.may_operate  # the first binding kept


def _owned_with_colleague(
    session: Session,
) -> tuple[Person, Person, int, ExerciseOperator]:
    """An exercise, its Owner and a colleague, and the colleague's grant as
    this request read it (held, so the session keeps that stale copy)."""
    owner = _operator(session, "o1", "ana@example.edu")
    colleague = _operator(session, "o2", "ben@example.edu")
    exercise = operators.create_exercise(session, Actor(owner), "abcdefghjk")
    operators.add_operator(session, exercise, Actor(owner), colleague)
    session.commit()
    grant = session.scalar(
        select(ExerciseOperator).where(ExerciseOperator.person_id == colleague.id)
    )
    assert grant is not None and not grant.is_owner
    # End this read's transaction, keeping the copy: SQLite (now with real
    # transactions) would otherwise lock the other session out, where
    # Postgres's read committed lets it write.
    session.commit()
    return owner, colleague, exercise.id, grant


def test_removing_someone_just_made_owner_is_refused(session: Session) -> None:
    """Codex on #4110: a removal racing a handover to the same person must
    not leave the exercise with no current Owner."""
    from applydesk.models import Exercise

    _, colleague, exercise_id, read = _owned_with_colleague(session)
    other = db.new_session()  # the super-admin hands over first
    ex, them = other.get(Exercise, exercise_id), other.get(Person, colleague.id)
    assert ex is not None and them is not None
    operators.hand_over(other, ex, SUPER, them)
    other.commit()
    other.close()
    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None
    with pytest.raises(Refused):  # caught on the fresh read, or by the conditional update
        operators.remove_operator(session, exercise, SUPER, colleague)
    assert read.is_owner  # the refusal reloaded the row
    session.rollback()
    assert operators.owner_of(session, exercise) == colleague


def test_handing_over_to_someone_just_removed_is_refused(session: Session) -> None:
    from applydesk.models import Exercise

    owner, colleague, exercise_id, read = _owned_with_colleague(session)
    other = db.new_session()  # the Owner removes them first
    ex, them = other.get(Exercise, exercise_id), other.get(Person, colleague.id)
    assert ex is not None and them is not None
    operators.remove_operator(other, ex, SUPER, them)
    other.commit()
    other.close()
    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None
    with pytest.raises(Refused):  # caught on the fresh read, or by the conditional update
        operators.hand_over(session, exercise, SUPER, colleague)
    session.rollback()
    assert operators.owner_of(session, exercise) == owner
    session.refresh(read)
    assert read.removed_at is not None and not read.is_owner


def test_two_first_sign_ins_of_one_account_both_get_its_person(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #4110: two requests resolving the same new account at once.
    This one looked before the other stored the account; its insert hits
    the unique (tenant, object ID), and it returns the other's person,
    keeping its own earlier work in the transaction."""
    other = db.new_session()  # the other request stores the account first
    first = people.resolve(other, _identity("o7", "gu@example.edu"))
    other.commit()
    assert first is not None
    first_id = first.id
    other.close()
    earlier = people.pending(session, "kept@example.edu", actor=None)  # unrelated, uncommitted

    looks = iter([None])
    real = people._bound_person  # pyright: ignore[reportPrivateUsage]  -- replay the stale look

    def stale_once(s: Session, tenant_id: str, object_id: str) -> Person | None:
        if next(looks, "real") is None:
            return None  # looked before the other request committed
        return real(s, tenant_id, object_id)

    monkeypatch.setattr(people, "_bound_person", stale_once)
    second = people.resolve(session, _identity("o7", "gu@example.edu"))
    session.commit()
    assert second is not None and second.id == first_id
    assert session.get(Person, earlier.id) is not None  # the savepoint undid only the insert


def test_a_rolled_back_resolve_leaves_nothing_behind(session: Session) -> None:
    """Codex on #4110: on SQLite the person's savepoint once committed on
    release, keeping the person but not its audit. The engine now begins a
    real transaction, so a rollback undoes both."""
    pending = people.pending(session, "ana@example.edu", actor=None)
    session.commit()
    assert people.resolve(session, _identity("o1", "new@example.edu")) is not None
    assert people.resolve(session, _identity("o2", "ana@example.edu")) is not None  # binds
    session.rollback()
    fresh = db.new_session()
    try:
        assert fresh.scalar(select(func.count()).select_from(Person)) == 1
        kept = fresh.get(Person, pending.id)
        assert kept is not None and not kept.bound
        assert [e.event_type for e in fresh.scalars(select(AuditEvent))] == ["person.created"]
    finally:
        fresh.close()


def test_a_former_owner_cannot_hand_over_after_losing_ownership(session: Session) -> None:
    """Codex on #4110: the Owner's authority is checked on fresh rows under
    the exercise's lock, and only the checked Owner is demoted, so an Owner
    whose ownership was just taken cannot appoint another."""
    from applydesk.models import Exercise

    owner, colleague, exercise_id, _ = _owned_with_colleague(session)
    third = _operator(session, "o3", "cy@example.edu")
    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None
    operators.add_operator(session, exercise, SUPER, third)
    session.commit()
    assert operators.owner_of(session, exercise) == owner  # this request's view
    session.commit()

    other = db.new_session()  # meanwhile the super-admin hands it to the colleague
    ex, them = other.get(Exercise, exercise_id), other.get(Person, colleague.id)
    assert ex is not None and them is not None
    operators.hand_over(other, ex, SUPER, them)
    other.commit()
    other.close()

    with pytest.raises(Refused, match="Only the exercise's Owner"):
        operators.hand_over(session, exercise, Actor(owner), third)
    session.rollback()
    assert operators.owner_of(session, exercise) == colleague


def test_a_check_passed_just_before_ownership_moved_still_demotes_no_one_else(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second guard: had the authority check passed a moment before the
    handover elsewhere, the demotion names the checked Owner, so it
    matches no row and the change is refused."""
    from applydesk.models import Exercise

    owner, colleague, exercise_id, _ = _owned_with_colleague(session)
    third = _operator(session, "o3", "cy@example.edu")
    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None
    operators.add_operator(session, exercise, SUPER, third)
    operators.hand_over(session, exercise, SUPER, colleague)  # ownership moves on
    session.commit()
    monkeypatch.setattr(operators, "_is_owner", lambda *_: True)  # the stale pass
    with pytest.raises(Refused, match="Ownership has just changed"):
        operators.hand_over(session, exercise, Actor(owner), third)
    session.rollback()
    assert operators.owner_of(session, exercise) == colleague


@pytest.mark.parametrize("change", ["add", "hand_over"])
def test_a_target_revoked_meanwhile_is_refused(session: Session, change: str) -> None:
    """Codex on #4110: the target's allowlisting is read fresh, so one
    revoked by another request since it was loaded is refused."""
    from applydesk.models import Exercise

    owner, colleague, exercise_id, _ = _owned_with_colleague(session)
    newcomer = _operator(session, "o4", "di@example.edu")
    session.commit()
    target = colleague if change == "hand_over" else newcomer
    assert target.may_operate  # this request's copy

    other = db.new_session()  # meanwhile the super-admin revokes them
    them = other.get(Person, target.id)
    assert them is not None
    operators.revoke(other, SUPER, them)
    other.commit()
    other.close()

    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None
    with pytest.raises(Refused, match="operator list"):
        if change == "hand_over":
            operators.hand_over(session, exercise, Actor(owner), target)
        else:
            operators.add_operator(session, exercise, Actor(owner), target)
    session.rollback()
    assert operators.owner_of(session, exercise) == owner


def test_an_actor_revoked_meanwhile_reaches_nothing_and_makes_nothing(session: Session) -> None:
    """Codex on #4110: every allowlist check reads the database, not the
    session's copy, so an actor revoked by another request is refused at
    once: no new exercise, no access, nothing listed."""
    owner, _, exercise_id, _ = _owned_with_colleague(session)
    from applydesk.models import Exercise

    exercise = session.get(Exercise, exercise_id)
    assert exercise is not None and owner.may_operate  # this request's copy
    session.commit()

    other = db.new_session()  # meanwhile the super-admin revokes them
    them = other.get(Person, owner.id)
    assert them is not None
    operators.revoke(other, SUPER, them)
    other.commit()
    other.close()

    with pytest.raises(Refused, match="operator list"):
        operators.create_exercise(session, Actor(owner), "bcdefghjkm")
    session.rollback()
    assert not operators.can_operate(session, exercise, Actor(owner))
    assert operators.operated_exercises(session, Actor(owner)) == []


def test_two_requests_adding_one_address_share_one_pending_person(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #4110: two requests adding one address at once. This one
    looked before the other committed; its insert hits the one-pending-
    per-address index and it returns the other's person, so an admission
    and a later sign-in meet on the same row."""
    other = db.new_session()  # the other request stores the address first
    first = people.pending(other, "ed@example.edu", actor=None)
    other.commit()
    first_id = first.id
    other.close()

    looks = iter([None])
    real = people._pending_person  # pyright: ignore[reportPrivateUsage]  -- replay the stale look

    def stale_once(s: Session, *keys: str | None) -> Person | None:
        if next(looks, "real") is None:
            return None  # looked before the other request committed
        return real(s, *keys)

    monkeypatch.setattr(people, "_pending_person", stale_once)
    second = people.pending(session, "Ed@Example.edu", actor=None)
    session.commit()
    assert second.id == first_id
    assert session.scalar(select(func.count()).select_from(Person)) == 1


def test_bound_people_may_still_share_an_address(session: Session) -> None:
    a = people.resolve(session, _identity("o1", "shared@example.edu"))
    b = people.resolve(session, _identity("o2", "shared@example.edu"))
    session.commit()
    assert a is not None and b is not None and a.id != b.id
