"""The operator check (segment AD2A, rung 4; rulings 73 and 75): the
operator's pages answer the super-admin, or someone on the allowlist, and
an exercise's pages only its current operators. Everyone else, a revoked
operator included, gets 404 on every operator route."""

from __future__ import annotations

import re
from datetime import UTC, datetime

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
SUPER = Actor(None, is_super_admin=True, platform=True)


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
        # The Lobby, New exercise and the Archive (AD2B) are lobby-level.
        lobby = (
            "/operator/exercises",
            "/operator/exercises/new",
            "/operator/exercises/archived",
            "/operator/exercises/panel",  # checks each ticked exercise itself (AD2B)
            "/operator/exercises/archived/restore",
        )
        if but_lobby and path in lobby:
            continue
        answer = client.request(method, "/applydesk" + path, follow_redirects=False)
        assert answer.status_code == 404, (method, path, answer.status_code)


def test_the_walk_covers_the_router() -> None:
    assert len(WALK) >= 15 and ("GET", f"/operator/exercises/{EX}") in WALK


def test_a_stranger_gets_404_everywhere(client: TestClient, unseeded: None) -> None:
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
    # Revoked as the list records it. The service refuses a sole Owner
    # (segment AD2O, `test_owners.py`); this tests what the gate does.
    me.may_operate, me.revoked_at = False, datetime.now(UTC)
    session.commit()
    _all_404(client)
    assert client.get("/applydesk/", follow_redirects=False).headers["location"].endswith("/me")
    operators.admit(session, SUPER, me)
    session.commit()
    session.close()
    assert client.get(f"/applydesk/operator/exercises/{EX}").status_code == 200  # grants kept


def test_the_allowlisted_with_no_exercise_reach_only_the_lobby(
    client: TestClient, unseeded: None
) -> None:
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


def test_a_new_scratch_exercise_gets_its_row_and_its_owner(
    client: TestClient, unseeded: None
) -> None:
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
    assert operators.owners_of(session, exercise) == [me]
    session.close()
    assert client.get(made.headers["location"]).status_code == 200


def test_a_stranger_cannot_make_a_scratch_exercise(client: TestClient, unseeded: None) -> None:
    made = client.post(
        "/applydesk/operator/exercises/new", data={"name": "Trial"}, follow_redirects=False
    )
    assert made.status_code == 404
    session = db.new_session()
    assert session.scalar(select(Exercise.id)) is None
    session.close()


def test_the_super_admin_s_scratch_exercise_is_owned_by_them(
    monkeypatch: pytest.MonkeyPatch, unseeded: None
) -> None:
    client = TestClient(host_with(("applydesk",))[0])  # the conftest's super-admin
    made = client.post(
        "/applydesk/operator/exercises/new", data={"name": "Trial"}, follow_redirects=False
    )
    public_id = made.headers["location"].rsplit("/", 1)[1]
    session = db.new_session()
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    assert exercise is not None
    (owner,) = operators.owners_of(session, exercise)
    assert owner.object_id == "local-dev" and not owner.may_operate
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


def test_a_deployed_operator_lands_on_the_lobby(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spec-writer at the close: deployed, an allowlisted operator who is not
    the super-admin lands on the Operator Lobby from `/`, not a 404; a
    stranger still gets 404 there."""
    from applydesk import gate

    session = db.new_session()
    seed.seed(session)
    session.close()
    monkeypatch.setattr(gate, "is_local", lambda: False)
    landed = client.get("/applydesk/", follow_redirects=False)
    assert landed.status_code == 302 and landed.headers["location"].endswith("/operator/exercises")
    assert client.get("/applydesk/operator", follow_redirects=False).status_code == 302
    monkeypatch.setattr(identity_settings, "fake_auth_principal_id", "someone-else")
    assert client.get("/applydesk/", follow_redirects=False).status_code == 404


def test_only_the_super_admin_reaches_the_admin_scaffolds(client: TestClient) -> None:
    for tab in ("exercises", "system"):
        assert client.get(f"/applydesk/admin/{tab}").status_code == 404


def test_admin_has_review_robin_s_three_tabs() -> None:
    """The author's ask (2026-11-21): Exercises Diagnostics and System
    Status beside Accounts Management, scaffolds for now. Each tab keeps
    where Back goes."""
    admin = TestClient(host_with(("applydesk",))[0])  # the conftest's super-admin
    back = f"/operator/exercises/{EX}"
    for tab in ("exercises", "operators", "system"):
        page = admin.get(f"/applydesk/admin/{tab}?return_to={back}").text
        strip = page[page.index('class="adm-tabs"') :]
        strip = strip[: strip.index("</nav>")]
        assert strip.count("data-admin-tab=") == 3
        assert f'data-admin-tab="{tab}"' in strip.split('aria-current="page"')[1][:40]
        for other in ("exercises", "operators", "system"):
            assert f'href="/applydesk/admin/{other}?return_to=/operator/exercises/{EX}"' in strip
        assert f'href="/applydesk{back}" data-admin-back' in page
    rows = admin.get("/applydesk/admin/exercises").text
    assert f'data-ex-row="{EX}"' in rows and "disabled" in rows
    # Review Robin's actions (the author's ruling): Manage opens Home.
    assert f'href="/applydesk/operator/exercises/{EX}" aria-label="Manage' in rows
    assert "Outbox" in rows and "Adopt" not in rows and "is not built yet" in rows


def test_exercises_diagnostics_names_each_owner_on_record(unseeded: None) -> None:
    """The author, 2026-11-22: the Owner column reads the database: none
    before the local seed runs, then the seeded Owner on every sample."""
    from applydesk import db, sample_data, seed

    admin = TestClient(host_with(("applydesk",))[0])

    def owner_cell(page: str, public_id: str) -> str:
        row = page[page.index(f'data-ex-row="{public_id}"') :]
        return row[: row.index("</tr>")].split("<td")[3]

    before = admin.get("/applydesk/admin/exercises").text
    assert all(
        "No Owner on record" in owner_cell(before, e.public_id) for e in sample_data.EXERCISES
    )
    session = db.new_session()
    seed.seed(session)
    session.close()
    after = admin.get("/applydesk/admin/exercises").text
    assert all(
        owner_cell(after, e.public_id) == ">Local Operator</td>\n        "
        for e in sample_data.EXERCISES
    )
    assert "each exercise's Owner" not in after  # the placeholder no longer lists it


def test_the_owner_columns_name_the_owner_not_the_viewer(unseeded: None) -> None:
    """Cold read, 2026-11-22: an Owner who is not the signed-in viewer
    shows on both pages, a pending one by address; a plain operator, an
    unknown exercise and a removed grant name no one."""
    from applydesk import db, operators, people, sample_data, seed
    from applydesk.models import Exercise

    session = db.new_session()
    seed.seed(session, owner_email="pat@example.edu")
    platform = operators.Actor(None, is_super_admin=True, platform=True)
    jane = people.pending(session, "jane.tan@example.edu", None)
    operators.admit(session, platform, jane)
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None
    operators.add_operator(session, ra, platform, jane)
    session.commit()
    ids = [e.public_id for e in sample_data.EXERCISES]
    labels = operators.owner_labels(session, [*ids, "nosuchid00"])
    assert labels == dict.fromkeys(ids, "pat@example.edu")  # Jane operates, Pat owns
    assert operators.owner_labels(session, []) == {}
    operators.remove_operator(session, ra, platform, jane)
    session.commit()
    assert operators.owner_labels(session, [EX]) == {EX: "pat@example.edu"}
    session.close()
    admin = TestClient(host_with(("applydesk",))[0])
    diag = admin.get("/applydesk/admin/exercises").text
    row = diag[diag.index(f'data-ex-row="{EX}"') :]
    assert "<td>pat@example.edu</td>" in row[: row.index("</tr>")]
    # The viewer sees RA in the Lobby once they operate it (segment AD2M:
    # the super-admin reaches only what they own or operate).
    assert "Recruitment and Selection" not in admin.get("/applydesk/operator/exercises").text
    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))  # bound above
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert me is not None and ra is not None
    operators.admit(session, platform, me)
    operators.add_operator(session, ra, platform, me)
    session.commit()
    session.close()
    lobby = admin.get("/applydesk/operator/exercises").text
    row = lobby[lobby.index("Recruitment and Selection") :]
    row = row[: row.index("</tr>")]
    # Your role (segment AD2O): the viewer operates RA, Pat owns it.
    assert '<td data-lb-role><span class="chip chip-mute">Operator</span>' in row


# --- The bug sweep at the AD2A close ---


def test_a_deployed_operator_is_not_offered_pages_that_would_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The author's ruling at the AD2A close: deployed, the participant's
    pages stay the super-admin's until a later AD2 segment, so an
    allowlisted operator's switcher offers no User Lobby and a dossier no
    *View as evaluators see it*; both stay 404 to them. Locally, both are
    offered and answer."""
    from applydesk import gate

    session = db.new_session()
    seed.seed(session)
    session.close()
    dossier = f"/applydesk/operator/exercises/{EX}/dossiers/p3bd7kq2wx"
    local_lobby = client.get("/applydesk/operator/exercises").text
    assert 'href="/applydesk/me"' in local_lobby
    assert "data-od-as-evaluators" in client.get(dossier).text
    monkeypatch.setattr(gate, "is_local", lambda: False)
    lobby = client.get("/applydesk/operator/exercises").text
    assert 'href="/applydesk/me"' not in lobby
    page = client.get(dossier)
    assert page.status_code == 200 and "data-od-as-evaluators" not in page.text
    assert client.get("/applydesk/me").status_code == 404
    assert client.get(f"/applydesk/me/exercises/{EX}/dossiers/p3bd7kq2wx").status_code == 404


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        # Not a pick from the suggestions: the page asks for one (AD2W).
        ("POST", "/applydesk/admin/operators/admit", "person_id=%C2%B2", 303),
        ("POST", "/applydesk/admin/operators/admit", "person_id=" + "9" * 30, 303),
        # The bulk bar drops a malformed ID, so nothing is ticked (AD2W).
        ("POST", "/applydesk/admin/operators/bulk", "action=revoke&person_ids=" + "1" * 31, 303),
        ("POST", "/applydesk/admin/operators/bulk", "action=revoke&person_ids=%C2%B2", 303),
        ("POST", f"/applydesk/operator/exercises/{EX}/operators/add", "person_id=%C2%B2", 400),
        ("POST", f"/applydesk/operator/exercises/{EX}/operators/add", "person_id=" + "9" * 30, 400),
        ("POST", f"/applydesk/operator/exercises/{EX}/operators/{'1' * 31}/remove", "", 422),
        ("POST", f"/applydesk/operator/exercises/{EX}/operators/{'1' * 31}/owner", "", 422),
    ],
)
def test_a_malformed_person_id_is_refused_not_a_500(
    method: str, path: str, body: str, status: int
) -> None:
    """`"²".isdigit()` is true and SQLite overflows past 64 bits: both
    were 500s."""
    admin = TestClient(host_with(("applydesk",))[0], raise_server_exceptions=False)
    answer = admin.request(
        method,
        path,
        content=body,
        headers={"content-type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert answer.status_code == status, answer.text[:200]


@pytest.mark.parametrize(
    ("return_to", "kept"),
    [
        (f"/operator/exercises/{EX}", True),
        (f"/operator/exercises/{EX}/process", True),
        ("/me", True),
        (f"/me/exercises/{EX}", True),
        ("/me/../../.auth/logout", False),
        (f"/operator/exercises/{EX}/../../../.auth/logout", False),
        ("/meX", False),
        (f"/operator/exercises/{EX}?x=1", False),
        (f"/operator/exercises/{EX}#top", False),
        ("/me\\..\\x", False),
    ],
)
def test_back_keeps_only_a_page_path(return_to: str, kept: bool) -> None:
    """A crafted `return_to` could aim Back at any path on the host, the
    sign-out among them; now only a page of Apply Desk's is kept."""
    from urllib.parse import quote

    admin = TestClient(host_with(("applydesk",))[0])
    page = admin.get(f"/applydesk/admin/operators?return_to={quote(return_to)}").text
    expected = return_to if kept else "/operator/exercises"
    assert f'href="/applydesk{expected}" data-admin-back' in page
