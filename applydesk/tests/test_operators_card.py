"""An exercise's Operators card, wired (segment AD2A, rung 8; ruling 73):
the Owner adds operators from the operator list, removes them and hands
ownership over, each audited; other operators see it read-only and are
refused; an exercise not yet loaded says so."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, operators, people, seed
from applydesk.models import AuditEvent, Exercise, Person
from applydesk.operators import Actor
from applydesk.tests._host import host_with
from cordware.identity import Identity
from cordware.settings import identity_settings

EX = "wa9juxbc2t"
HOME = f"/applydesk/operator/exercises/{EX}"
SUPER = Actor(None, is_super_admin=True, platform=True)


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
    assert (
        "An Owner is made an operator before being removed"
        in owner.get(refused.headers["location"]).text
    )


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


def test_an_exercise_not_loaded_is_reached_by_no_one(unseeded: None) -> None:
    """Segment AD2M: with an empty database even the super-admin holds no
    role on a sample, so its pages are a 404; Exercises Diagnostics' Manage
    says it is not loaded and how to load it."""
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get(HOME).status_code == 404
    manage = client.post(f"/applydesk/admin/exercises/{EX}/manage", follow_redirects=False)
    assert manage.headers["location"].endswith("said=not_loaded")
    assert "python -m applydesk.seed" in client.get(manage.headers["location"]).text


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
    admins = {"already_admin", "not_admin", "last_admin", "pending", "is_admin", "protected"}
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


# --- AD2O's scaffold: Owners and operators -------------------------------------


def test_the_card_offers_each_viewer_only_their_moves(owner: TestClient) -> None:
    """`applydesk/spec/permissions.md` §7: an Owner sees Make Owner, Transfer
    and Remove on an operator, and, as the only Owner, no Step down on their
    own row."""
    ben = _colleague()
    session = db.new_session()
    ra = session.scalars(select(Exercise).where(Exercise.public_id == EX)).one()
    person = session.get(Person, ben)
    assert person is not None
    operators.add_operator(session, ra, SUPER, person)
    session.commit()
    session.close()
    page = owner.get(HOME).text
    card = page[
        page.index("data-operators") : page.index("</section>", page.index("data-operators"))
    ]
    assert '<h2 id="ops-h">Owners and operators</h2>' in card
    row = card[card.index(f'data-ops-row="{ben}"') :]
    row = row[: row.index("</tr>")]
    assert 'data-ops-move="make-owner"' in row and "disabled" not in row  # wired (rung 4)
    assert 'data-ops-move="transfer"' in row and 'data-ops-move="remove"' in row
    me = card[card.index("data-ops-self") :]
    me = me[: me.index("</tr>")]
    assert "data-ops-last" in me and 'data-ops-move="step-down"' not in me


# --- AD2O wired: each move posts and says how it went ---------------------------


def _add(ben: int) -> None:
    session = db.new_session()
    ra = session.scalars(select(Exercise).where(Exercise.public_id == EX)).one()
    person = session.get(Person, ben)
    assert person is not None
    operators.add_operator(session, ra, SUPER, person)
    session.commit()
    session.close()


def test_make_owner_then_make_operator_from_the_card(owner: TestClient) -> None:
    ben = _colleague()
    _add(ben)
    made = owner.post(f"{HOME}/operators/{ben}/make-owner", follow_redirects=False)
    assert made.headers["location"].endswith("ops_said=made_owner#operators")
    assert _roles()[ben] is True
    page = owner.get(made.headers["location"]).text
    assert "Made an Owner." in page and 'data-ops-move="step-down"' in page
    back = owner.post(f"{HOME}/operators/{ben}/demote", follow_redirects=False)
    assert back.headers["location"].endswith("ops_said=demoted#operators")
    assert _roles()[ben] is False


def test_the_only_owner_cannot_step_down_but_can_once_another_owns(owner: TestClient) -> None:
    me = next(pid for pid, is_owner in _roles().items() if is_owner)
    refused = owner.post(f"{HOME}/operators/{me}/step-down", follow_redirects=False)
    assert refused.headers["location"].endswith("ops_said=last_owner#operators")
    ben = _colleague()
    _add(ben)
    owner.post(f"{HOME}/operators/{ben}/make-owner")
    done = owner.post(f"{HOME}/operators/{me}/step-down", follow_redirects=False)
    assert done.headers["location"].endswith("ops_said=stepped_down#operators")
    assert _roles()[me] is False


def test_leaving_lands_on_the_lobby(owner: TestClient) -> None:
    me = next(pid for pid, is_owner in _roles().items() if is_owner)
    ben = _colleague()
    _add(ben)
    owner.post(f"{HOME}/operators/{ben}/make-owner")
    owner.post(f"{HOME}/operators/{me}/step-down")
    left = owner.post(f"{HOME}/operators/{me}/leave", follow_redirects=False)
    assert left.headers["location"].endswith("/operator/exercises?said=left")
    assert me not in _roles()
    assert "You left the exercise." in owner.get(left.headers["location"]).text


def test_nobody_leaves_for_someone_else(owner: TestClient) -> None:
    ben = _colleague()
    _add(ben)
    refused = owner.post(f"{HOME}/operators/{ben}/leave", follow_redirects=False)
    assert refused.headers["location"].endswith("ops_said=not_self#operators")
    assert ben in _roles()


def test_the_lobby_rows_carry_the_viewer_s_role(owner: TestClient) -> None:
    lobby = owner.get("/applydesk/operator/exercises").text
    assert f'data-id="{EX}"' in lobby and 'data-owner="true"' in lobby
    assert "data-lb-owner-note" in lobby


def test_an_operator_sees_only_leave_on_their_own_row(owner: TestClient) -> None:
    """Cold read: §7's operator column. Ownership passes to Ben, so the
    viewer operates: Leave on their row, nothing on Ben's; and in the Lobby
    their row for RA says they do not own it."""
    ben = _colleague()
    _add(ben)
    owner.post(f"{HOME}/operators/{ben}/owner")  # transfer: the viewer operates now
    page = owner.get(HOME).text
    card = page[
        page.index("data-operators") : page.index("</section>", page.index("data-operators"))
    ]
    me = card[card.index("data-ops-self") :]
    me = me[: me.index("</tr>")]
    assert 'data-ops-move="leave"' in me
    them = card[card.index(f'data-ops-row="{ben}"') :]
    them = them[: them.index("</tr>")]
    assert "data-ops-move" not in them
    lobby = owner.get("/applydesk/operator/exercises").text
    row = lobby[lobby.index(f'data-id="{EX}"') :]
    assert 'data-owner="false"' in row[: row.index(">")]


def test_step_down_is_for_your_own_row_only(owner: TestClient) -> None:
    ben = _colleague()
    _add(ben)
    owner.post(f"{HOME}/operators/{ben}/make-owner")
    refused = owner.post(f"{HOME}/operators/{ben}/step-down", follow_redirects=False)
    assert refused.headers["location"].endswith("ops_said=not_self#operators")
    assert _roles()[ben] is True
