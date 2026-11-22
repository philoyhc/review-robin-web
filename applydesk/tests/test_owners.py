"""An exercise's several Owners and their moves (segment AD2O,
`applydesk/spec/permissions.md` §3 and §8): Make Owner, Transfer, Demote
and Step down, Leave; never without an Owner; Revoke refused for a sole
Owner of a live exercise. Each move audited."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import db, operators, people
from applydesk.models import AuditEvent, Exercise, Person
from applydesk.operators import Actor, Refused
from cordware.identity import Identity
from cordware.settings import identity_settings

pytestmark = pytest.mark.usefixtures("unseeded")

SUPER = Actor(person=None, is_super_admin=True, platform=True)


@pytest.fixture
def session(applydesk_db: None) -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _person(session: Session, oid: str) -> Person:
    person = people.resolve(
        session,
        Identity(principal_id=oid, email=f"{oid}@x.edu", name=oid, tenant_id="t"),
    )
    assert person is not None
    operators.admit(session, SUPER, person)
    session.flush()
    return person


def _exercise(session: Session) -> tuple[Exercise, Person, Person, Person]:
    """An exercise Owned by Ann, with Ben and Cat as operators."""
    ann, ben, cat = (_person(session, n) for n in ("ann", "ben", "cat"))
    exercise = operators.create_exercise(session, Actor(ann), "ex0000own1")
    operators.add_operator(session, exercise, Actor(ann), ben)
    operators.add_operator(session, exercise, Actor(ann), cat)
    session.commit()
    return exercise, ann, ben, cat


def _roles(session: Session, exercise: Exercise) -> dict[str, bool]:
    return {p.label: owner for p, owner in operators.current_operators(session, exercise)}


def _events(session: Session, kind: str) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(AuditEvent).where(AuditEvent.event_type == kind)
        )
        or 0
    )


def test_make_owner_adds_an_owner_beside_the_others(session: Session) -> None:
    exercise, ann, ben, _ = _exercise(session)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    assert _roles(session, exercise) == {"ann": True, "ben": True, "cat": False}
    assert _events(session, "exercise.owner_added") == 1
    with pytest.raises(Refused) as already:
        operators.make_owner(session, exercise, Actor(ann), ben)
    assert already.value.key == "already_owner"


def test_an_operator_makes_no_one_an_owner(session: Session) -> None:
    exercise, _, ben, cat = _exercise(session)
    with pytest.raises(Refused) as no:
        operators.make_owner(session, exercise, Actor(ben), cat)
    assert no.value.key == "not_owner"


def test_demote_and_step_down_but_never_the_last_owner(session: Session) -> None:
    exercise, ann, ben, _ = _exercise(session)
    with pytest.raises(Refused) as last:
        operators.demote_owner(session, exercise, Actor(ann), ann)  # the only Owner
    assert last.value.key == "last_owner"
    session.rollback()
    operators.make_owner(session, exercise, Actor(ann), ben)
    operators.demote_owner(session, exercise, Actor(ann), ann)  # Ann steps down
    session.commit()
    assert _roles(session, exercise) == {"ann": False, "ben": True, "cat": False}
    event = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "exercise.owner_demoted")
    ).one()
    assert event.detail["context"]["stepped_down"] is True
    with pytest.raises(Refused) as last_again:
        operators.demote_owner(session, exercise, Actor(ben), ben)
    assert last_again.value.key == "last_owner"


def test_a_demoted_owner_demotes_no_one(session: Session) -> None:
    """Sequential: once Ann made Ben an operator, Ben (no Owner now) cannot
    demote Ann; one Owner remains. The concurrent case is the next test."""
    exercise, ann, ben, _ = _exercise(session)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    operators.demote_owner(session, exercise, Actor(ann), ben)
    session.commit()
    with pytest.raises(Refused) as refused:
        operators.demote_owner(session, exercise, Actor(ben), ann)  # Ben is no Owner now
    assert refused.value.key == "not_owner"
    assert sum(_roles(session, exercise).values()) == 1


def test_leave_takes_an_operator_off_but_not_an_owner(session: Session) -> None:
    exercise, ann, _, cat = _exercise(session)
    operators.leave(session, exercise, Actor(cat))
    session.commit()
    assert "cat" not in _roles(session, exercise)
    assert _events(session, "exercise.operator_left") == 1
    with pytest.raises(Refused) as owner:
        operators.leave(session, exercise, Actor(ann))
    assert owner.value.key == "owner_leaving"


def test_the_last_owner_may_transfer(session: Session) -> None:
    exercise, ann, ben, _ = _exercise(session)
    operators.transfer(session, exercise, Actor(ann), ben)
    session.commit()
    assert _roles(session, exercise) == {"ann": False, "ben": True, "cat": False}


def test_an_owner_is_demoted_before_removal(session: Session) -> None:
    exercise, ann, ben, _ = _exercise(session)
    operators.make_owner(session, exercise, Actor(ann), ben)
    with pytest.raises(Refused) as owner:
        operators.remove_operator(session, exercise, Actor(ann), ben)
    assert owner.value.key == "is_owner"


def test_an_archived_exercise_refuses_every_move(session: Session) -> None:
    exercise, ann, ben, cat = _exercise(session)
    exercise.archived_at = datetime.now(UTC)
    session.commit()
    for move in (
        lambda: operators.make_owner(session, exercise, Actor(ann), ben),
        lambda: operators.transfer(session, exercise, Actor(ann), ben),
        lambda: operators.remove_operator(session, exercise, Actor(ann), cat),
        lambda: operators.leave(session, exercise, Actor(cat)),
        lambda: operators.demote_owner(session, exercise, Actor(ann), ann),
    ):
        with pytest.raises(Refused) as no:
            move()
        assert no.value.key == "archived"
        session.rollback()


def test_revoke_refuses_a_sole_owner_of_a_live_exercise(session: Session) -> None:
    exercise, ann, ben, _ = _exercise(session)
    with pytest.raises(Refused) as sole:
        operators.revoke(session, SUPER, ann)
    assert sole.value.key == "sole_owner"
    session.rollback()
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    operators.revoke(session, SUPER, ann)  # not the only Owner now
    session.commit()
    with pytest.raises(Refused) as now_sole:
        operators.revoke(session, SUPER, ben)  # Ann is revoked: Ben is the one who can act
    assert now_sole.value.key == "sole_owner"


def test_an_archived_exercise_does_not_hold_revoke(session: Session) -> None:
    exercise, ann, _, _ = _exercise(session)
    exercise.archived_at = datetime.now(UTC)
    session.commit()
    operators.revoke(session, SUPER, ann)
    session.commit()


def test_a_revoked_owner_does_not_count_toward_the_guard(session: Session) -> None:
    """Ann is revoked but keeps her grant: Ben is the only Owner who can
    act, so he may not step down."""
    exercise, ann, ben, _ = _exercise(session)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    operators.revoke(session, SUPER, ann)
    session.commit()
    with pytest.raises(Refused) as last:
        operators.demote_owner(session, exercise, Actor(ben), ben)
    assert last.value.key == "last_owner"


def test_two_owners_demoting_each_other_at_once_leave_one(session: Session) -> None:
    """Two sessions: Ann's demote of Ben commits while Ben's session holds
    a stale view; Ben's demote of Ann, taken under the row lock, reads Ben's
    grant fresh and is refused, so one Owner remains."""
    exercise, ann, ben, _ = _exercise(session)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    other = db.new_session()
    ben_there = other.get(Person, ben.id)
    ann_there = other.get(Person, ann.id)
    ex_there = other.get(Exercise, exercise.id)
    assert ben_there is not None and ann_there is not None and ex_there is not None
    other.commit()  # SQLite: end the read so the first session may write
    operators.demote_owner(session, exercise, Actor(ann), ben)
    session.commit()
    with pytest.raises(Refused):
        operators.demote_owner(other, ex_there, Actor(ben_there), ann_there)
    other.rollback()
    other.close()
    assert sum(_roles(session, exercise).values()) == 1


def test_a_pending_owner_does_not_keep_the_exercise_run(session: Session) -> None:
    """Cold read: a never-signed-in Owner reaches nothing, so the last Owner
    who can act may not step down beside one; demoting the pending one is
    allowed (it takes no acting Owner away)."""
    exercise, ann, _, _ = _exercise(session)
    pat = people.pending(session, "pat@x.edu", actor=None)
    operators.admit(session, SUPER, pat)
    operators.add_operator(session, exercise, Actor(ann), pat)
    operators.make_owner(session, exercise, Actor(ann), pat)
    session.commit()
    with pytest.raises(Refused) as last:
        operators.demote_owner(session, exercise, Actor(ann), ann)
    assert last.value.key == "last_owner"
    session.rollback()
    operators.demote_owner(session, exercise, Actor(ann), pat)
    session.commit()


def test_a_revoke_refused_after_its_update_changes_nothing(session: Session) -> None:
    """Cold read: the re-check after Revoke's update puts the row back, so a
    bulk batch's transaction keeps nothing of a refused revoke."""
    exercise, ann, ben, _ = _exercise(session)
    # Ben owns alone after a transfer the first check did not see.
    operators.transfer(session, exercise, Actor(ann), ben)
    session.commit()
    with pytest.raises(Refused):
        operators.revoke(session, SUPER, ben)
    session.commit()
    session.refresh(ben)
    assert ben.may_operate and ben.revoked_at is None


def test_an_adopting_super_admin_counts_as_an_owner(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #4145: the super-admin adopts unlisted (their grants count
    without `may_operate`), so beside them Ann may step down."""
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["root@x.edu"])
    exercise, ann, _, _ = _exercise(session)
    root = people.resolve(
        session, Identity(principal_id="root", email="root@x.edu", name="root", tenant_id="t")
    )
    assert root is not None
    root.may_operate = False  # unlisted
    session.flush()
    operators.adopt(session, exercise, Actor(root, is_super_admin=True))
    operators.demote_owner(session, exercise, Actor(ann), ann)
    session.commit()
    assert _roles(session, exercise) == {"ann": False, "ben": False, "cat": False, "root": True}


def test_a_move_reads_the_archive_under_the_lock(session: Session) -> None:
    """Codex on #4145: a copy loaded before another request archived the
    exercise still reads live; the move re-reads it under the lock."""
    exercise, ann, ben, _ = _exercise(session)
    other = db.new_session()
    there = other.get(Exercise, exercise.id)
    assert there is not None
    there.archived_at = datetime.now(UTC)
    other.commit()
    other.close()
    assert exercise.archived_at is None  # this session's copy, loaded before
    with pytest.raises(Refused) as no:
        operators.make_owner(session, exercise, Actor(ann), ben)
    assert no.value.key == "archived"
