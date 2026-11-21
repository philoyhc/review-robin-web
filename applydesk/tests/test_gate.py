"""The operator check (segment AD2A, rung 4; rulings 73 and 75): the
operator's pages answer the super-admin, or someone on the allowlist, and
an exercise's pages only its current operators. Everyone else, a revoked
operator included, gets 404 on every operator route."""

from __future__ import annotations

import re

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, operators, routes_operator, seed
from applydesk.models import Exercise, ExerciseOperator, Person
from applydesk.operators import Actor
from applydesk.tests._host import host_with
from cordware.settings import identity_settings

EX = "wa9juxbc2t"  # a sample exercise the seed grants
OTHER = "r6tm4kq9wz"
SUPER = Actor(None, is_super_admin=True)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Signed in as the fake identity, no longer the super-admin."""
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    return TestClient(host_with(("applydesk",))[0])


def _me() -> Person | None:
    session = db.new_session()
    try:
        return session.scalar(select(Person).where(Person.object_id == "local-dev"))
    finally:
        session.close()


def _operator_paths() -> list[tuple[str, str]]:
    """Every operator route, its parameters filled with well-formed values
    on `EX`: (method, path)."""
    walked: list[tuple[str, str]] = []
    for route in routes_operator.router.routes:
        assert isinstance(route, APIRoute)
        path = route.path.replace("{exercise_id}", EX)
        path = re.sub(r"\{[a-z_]+\}", "process", path)
        walked.extend((method, path) for method in sorted(route.methods or ()))
    return walked


WALK = _operator_paths()


def _all_404(client: TestClient, *, but_lobby: bool = False) -> None:
    for method, path in WALK:
        if but_lobby and path in ("/operator/exercises", "/operator/exercises/new"):
            continue
        answer = client.request(method, "/applydesk" + path, follow_redirects=False)
        assert answer.status_code == 404, (method, path, answer.status_code)


def test_the_walk_covers_the_router() -> None:
    assert len(WALK) >= 15 and ("GET", f"/operator/exercises/{EX}") in WALK


def test_a_stranger_gets_404_everywhere(client: TestClient) -> None:
    _all_404(client)
    me = _me()
    assert me is not None and not me.may_operate  # bound at sign-in, not allowlisted


def test_the_allowlisted_reach_only_their_exercises(client: TestClient) -> None:
    session = db.new_session()
    seed.seed(session)  # allowlists the fake identity; Owner of every sample
    session.close()
    assert client.get(f"/applydesk/operator/exercises/{EX}").status_code == 200
    session = db.new_session()
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == OTHER))
    assert exercise is not None
    grant = session.scalar(
        select(ExerciseOperator).where(ExerciseOperator.exercise_id == exercise.id)
    )
    assert grant is not None
    session.delete(grant)  # no longer an operator of OTHER
    session.commit()
    session.close()
    assert client.get(f"/applydesk/operator/exercises/{OTHER}").status_code == 404
    lobby = client.get("/applydesk/operator/exercises").text
    assert f"/exercises/{EX}" in lobby and f"/exercises/{OTHER}" not in lobby
    assert (
        client.get("/applydesk/", follow_redirects=False)
        .headers["location"]
        .endswith("/operator/exercises")
    )


def test_a_revoked_operator_gets_404_everywhere_and_back_when_readmitted(
    client: TestClient,
) -> None:
    session = db.new_session()
    seed.seed(session)
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    assert me is not None
    operators.revoke(session, SUPER, me)
    session.commit()
    _all_404(client)
    assert client.get("/applydesk/", follow_redirects=False).headers["location"].endswith("/me")
    operators.admit(session, SUPER, me)
    session.commit()
    session.close()
    assert client.get(f"/applydesk/operator/exercises/{EX}").status_code == 200  # grants kept


def test_the_allowlisted_with_no_exercise_reach_only_the_lobby(client: TestClient) -> None:
    client.get("/applydesk/")  # binds the fake identity
    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    assert me is not None
    operators.admit(session, SUPER, me)
    session.commit()
    session.close()
    _all_404(client, but_lobby=True)
    lobby = client.get("/applydesk/operator/exercises")
    assert lobby.status_code == 200 and f"/exercises/{EX}" not in lobby.text


def test_a_new_scratch_exercise_gets_its_row_and_its_owner(client: TestClient) -> None:
    client.get("/applydesk/")
    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    assert me is not None
    operators.admit(session, SUPER, me)
    session.commit()
    made = client.post(
        "/applydesk/operator/exercises/new", data={"name": "Trial"}, follow_redirects=False
    )
    assert made.status_code == 303
    public_id = made.headers["location"].rsplit("/", 1)[1]
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    assert exercise is not None
    assert operators.owner_of(session, exercise) == me
    session.close()
    assert client.get(made.headers["location"]).status_code == 200


def test_a_stranger_cannot_make_a_scratch_exercise(client: TestClient) -> None:
    made = client.post(
        "/applydesk/operator/exercises/new", data={"name": "Trial"}, follow_redirects=False
    )
    assert made.status_code == 404
    session = db.new_session()
    assert session.scalar(select(Exercise.id)) is None
    session.close()


def test_the_super_admin_s_scratch_exercise_is_owned_by_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(host_with(("applydesk",))[0])  # the conftest's super-admin
    made = client.post(
        "/applydesk/operator/exercises/new", data={"name": "Trial"}, follow_redirects=False
    )
    public_id = made.headers["location"].rsplit("/", 1)[1]
    session = db.new_session()
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    assert exercise is not None
    owner = operators.owner_of(session, exercise)
    assert owner is not None and owner.object_id == "local-dev" and not owner.may_operate
    session.close()


# --- Rung 5: the operator list, the super-admin's page ---


def test_only_the_super_admin_reaches_the_operator_list(client: TestClient) -> None:
    """Ruling 75: an operator, even an Owner of every sample, gets 404, and
    the account menu offers them no Admin."""
    session = db.new_session()
    seed.seed(session)
    session.close()
    assert client.get("/applydesk/admin/operators").status_code == 404
    lobby = client.get("/applydesk/operator/exercises").text
    assert "data-admin-entry" not in lobby


def test_the_super_admin_reaches_admin_from_the_account_menu() -> None:
    """As Review Robin's Admin (`cordware/spec/header_chrome.md` §4): an
    account-menu entry carrying the page to come back to, not in the
    switcher, and not on the Admin page itself."""
    client = TestClient(host_with(("applydesk",))[0])  # the conftest's super-admin
    lobby = client.get("/applydesk/operator/exercises").text
    entry = 'href="/applydesk/admin/operators?return_to=/operator/exercises" data-admin-entry'
    assert entry in lobby
    switcher = lobby[lobby.index('class="switch"') :]
    switcher = switcher[: switcher.index("</details>")]
    assert "/admin/operators" not in switcher
    page = client.get(f"/applydesk/admin/operators?return_to=/operator/exercises/{EX}")
    assert page.status_code == 200
    assert "<h1>Admin</h1>" in page.text and "data-admin-entry" not in page.text
    assert f'href="/applydesk/operator/exercises/{EX}" data-admin-back' in page.text
    away = client.get("/applydesk/admin/operators?return_to=//evil.example").text
    assert 'href="/applydesk/operator/exercises" data-admin-back' in away  # only Apply Desk paths


# --- Rung 7: the Operators card on Home (wired at rung 8: test_operators_card.py) ---


def test_home_shows_the_operators_card_under_details() -> None:
    client = TestClient(host_with(("applydesk",))[0])
    page = client.get(f"/applydesk/operator/exercises/{EX}").text
    side = page[page.index('class="hm-side"') :]
    assert side.index("data-details") < side.index("data-operators")


def test_every_exercise_route_names_its_parameter_exercise_id() -> None:
    """Cold read: the check reads `exercise_id` from the path, so a route
    under /operator/exercises/{…} naming it otherwise would pass with the
    allowlist check alone."""
    from applydesk import routes_operator

    for route in routes_operator.router.routes:
        assert isinstance(route, APIRoute)
        if route.path.startswith("/operator/exercises/{"):
            assert route.path.startswith("/operator/exercises/{exercise_id}"), route.path


def test_the_audit_warning_carries_its_event_fields(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Outside strict mode a bad detail writes through and is logged with
    Review Robin's structured fields (cold read)."""
    import logging

    from applydesk import audit

    monkeypatch.setattr(audit, "_strict", lambda: False)
    session = db.new_session()
    with caplog.at_level(logging.WARNING, logger="applydesk.audit"):
        audit.write_event(session, event_type="no.such.type", actor=None)
    session.close()
    record = next(r for r in caplog.records if r.name == "applydesk.audit")
    assert getattr(record, "event", None) == "audit.detail_schema_violation"
    assert getattr(record, "event_type", None) == "no.such.type"
