"""An exercise's Operators card, wired (segment AD2A, rung 8; ruling 73):
the Owner adds operators from the operator list, removes them and hands
ownership over, each audited; other operators see it read-only and are
refused; an exercise not yet loaded says so."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, operators, people, seed
from applydesk.models import AuditEvent, Exercise
from applydesk.operators import Actor
from applydesk.tests._host import host_with
from cordware.identity import Identity
from cordware.settings import identity_settings

EX = "wa9juxbc2t"
HOME = f"/applydesk/operator/exercises/{EX}"
SUPER = Actor(None, is_super_admin=True)


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """The fake identity, not the super-admin, Owner of every sample."""
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    session = db.new_session()
    seed.seed(session)
    session.close()
    return TestClient(host_with(("applydesk",))[0])


def _colleague(email: str = "ben@example.edu", oid: str = "o-ben") -> int:
    """Someone on the operator list, bound, who has signed in."""
    session = db.new_session()
    person = people.resolve(
        session,
        Identity(principal_id=oid, email=email, name="Ben Ong", tenant_id="local-tenant"),
    )
    assert person is not None
    operators.admit(session, SUPER, person)
    session.commit()
    pid = person.id
    session.close()
    return pid


def _roles() -> dict[int, bool]:
    session = db.new_session()
    try:
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == EX))
        assert exercise is not None
        return {p.id: o for p, o in operators.current_operators(session, exercise)}
    finally:
        session.close()


def test_the_owner_adds_from_the_list_then_hands_over(owner: TestClient) -> None:
    ben = _colleague()
    found = owner.get(HOME, params={"op_q": "ben"}).text
    assert "data-ops-manage" in found and "data-ops-hit" in found and "Ben Ong" in found
    added = owner.post(
        f"{HOME}/operators/add", data={"person_id": str(ben)}, follow_redirects=False
    )
    assert added.headers["location"].endswith("ops_said=added#operators")
    assert _roles()[ben] is False
    again = owner.get(HOME, params={"op_q": "ben"}).text
    assert "data-ops-hit" not in again  # already an operator: not offered
    made = owner.post(f"{HOME}/operators/{ben}/owner", follow_redirects=False)
    assert made.headers["location"].endswith("ops_said=owner#operators")
    roles = _roles()
    assert roles[ben] is True and list(roles.values()).count(True) == 1
    now = owner.get(HOME).text  # the former Owner stays, read-only now
    assert "data-ops-manage" not in now and f'data-ops-row="{ben}"' in now
    session = db.new_session()
    kinds = [e.event_type for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    session.close()
    assert kinds[-2:] == ["exercise.operator_added", "exercise.ownership_handed_over"]


def test_the_owner_removes_but_not_themself(owner: TestClient) -> None:
    ben = _colleague()
    owner.post(f"{HOME}/operators/add", data={"person_id": str(ben)})
    gone = owner.post(f"{HOME}/operators/{ben}/remove", follow_redirects=False)
    assert gone.headers["location"].endswith("ops_said=removed#operators")
    assert ben not in _roles()
    me = next(pid for pid, is_owner in _roles().items() if is_owner)
    refused = owner.post(f"{HOME}/operators/{me}/remove", follow_redirects=False)
    assert refused.headers["location"].endswith("ops_said=is_owner#operators")
    assert "The Owner cannot be removed" in owner.get(refused.headers["location"]).text


def test_someone_off_the_list_cannot_be_added(owner: TestClient) -> None:
    session = db.new_session()
    stranger = people.pending(session, "cy@example.edu", actor=None)
    session.commit()
    sid = stranger.id
    session.close()
    assert owner.get(HOME, params={"op_q": "cy@"}).text.count("data-ops-hit") == 0
    refused = owner.post(
        f"{HOME}/operators/add", data={"person_id": str(sid)}, follow_redirects=False
    )
    assert refused.headers["location"].endswith("ops_said=not_listed#operators")


def test_an_operator_who_is_not_the_owner_sees_it_read_only_and_is_refused(
    owner: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    ben = _colleague()
    owner.post(f"{HOME}/operators/add", data={"person_id": str(ben)})
    me = next(pid for pid, is_owner in _roles().items() if is_owner)
    # Sign in as Ben, an operator but not the Owner.
    monkeypatch.setattr(identity_settings, "fake_auth_principal_id", "o-ben")
    monkeypatch.setattr(identity_settings, "fake_auth_email", "ben@example.edu")
    as_ben = TestClient(host_with(("applydesk",))[0])
    page = as_ben.get(HOME).text
    assert "data-operators" in page and "data-ops-manage" not in page
    refused = as_ben.post(f"{HOME}/operators/{me}/remove", follow_redirects=False)
    assert refused.headers["location"].endswith("ops_said=not_owner#operators")
    assert me in _roles()


def test_an_exercise_not_loaded_says_so() -> None:
    """The conftest's super-admin, with an empty database: no rows yet."""
    page = TestClient(host_with(("applydesk",))[0]).get(HOME).text
    assert "data-ops-unrecorded" in page and "python -m applydesk.seed" in page


def test_every_refusal_key_has_a_status_line() -> None:
    """Cold read: refusals are shown by key, never by matching their text,
    so each key a service can raise has a line on the page that shows it."""
    import ast
    from pathlib import Path

    from applydesk import routes_admin, routes_operator

    root = Path(__file__).resolve().parents[1]
    keys: dict[str, set[str]] = {}
    for name in ("operators.py", "allowlist.py", "team.py"):
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", getattr(node.func, "id", "")) == "Refused"
            ):
                for kw in node.keywords:
                    if kw.arg == "key" and isinstance(kw.value, ast.Constant):
                        keys.setdefault(name, set()).add(str(kw.value.value))
    # The admin page shows the allowlist's; the card shows an exercise's.
    # Admins' keys (segment AD2M) are the admin page's alone.
    admins = {"already_admin", "not_admin", "last_admin", "pending", "is_admin"}
    admin = keys["allowlist.py"] | {"already_listed", "not_listed", "not_super_admin"} | admins
    card = keys["team.py"] | (keys["operators.py"] - {"already_listed", "not_super_admin"} - admins)
    assert admin <= routes_admin.SAID.keys(), admin - routes_admin.SAID.keys()
    assert card <= routes_operator.OPS_SAID.keys(), card - routes_operator.OPS_SAID.keys()


def test_sqlite_busy_is_reported_as_a_concurrent_change(
    owner: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """On SQLite two requests that both read, then write, meet as
    "database is locked": reported as a concurrent change, not a 500
    (bug sweep at the AD2A close). Any other operational error is not
    swallowed."""
    from sqlalchemy.exc import OperationalError

    from applydesk import team

    ben = _colleague()

    def busy(*_args: object) -> None:
        raise OperationalError("UPDATE", {}, Exception("database is locked"))

    monkeypatch.setattr(team, "remove", busy)
    answer = owner.post(f"{HOME}/operators/{ben}/remove", follow_redirects=False)
    assert answer.headers["location"].endswith("ops_said=changed#operators")

    def broken(*_args: object) -> None:
        raise OperationalError("UPDATE", {}, Exception("disk I/O error"))

    monkeypatch.setattr(team, "remove", broken)
    with pytest.raises(OperationalError):
        owner.post(f"{HOME}/operators/{ben}/remove", follow_redirects=False)

    from sqlalchemy.exc import IntegrityError

    def clash(*_args: object) -> None:
        raise IntegrityError("UPDATE", {}, Exception("UNIQUE constraint failed: x"))

    monkeypatch.setattr(team, "remove", clash)
    answer = owner.post(f"{HOME}/operators/{ben}/remove", follow_redirects=False)
    assert answer.headers["location"].endswith("ops_said=changed#operators")

    def not_null(*_args: object) -> None:
        raise IntegrityError("UPDATE", {}, Exception("NOT NULL constraint failed: x"))

    monkeypatch.setattr(team, "remove", not_null)  # a bug, not a race: it stays one
    with pytest.raises(IntegrityError):
        owner.post(f"{HOME}/operators/{ben}/remove", follow_redirects=False)
