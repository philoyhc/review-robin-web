"""The localhost seed's scenarios (segment AD2X): built by posting what the
pages post, as Local Operator; a second run changes nothing."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from applydesk import db, local_seed, panels_store, stages, workflow
from applydesk.lookups import exercise_or_404
from applydesk.models import Application, Exercise
from applydesk.tests._host import host_with
from cordware.settings import identity_settings

pytestmark = pytest.mark.usefixtures("applydesk_db")


@pytest.fixture(autouse=True)
def _second_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "divya.petrova@example.edu")
    monkeypatch.setattr(identity_settings, "fake_auth_alt_name", "Divya Petrova")


def _open_form() -> local_seed.Made:
    return next(m for m in local_seed.seed_local() if m.name == local_seed.OPEN_FORM)


def test_the_open_form_scenario() -> None:
    made = _open_form()
    assert made.made
    plan = stages.plan_of(made.public_id)
    assert plan.stages[0].status == "Published" and plan.stages[0].form
    session = db.new_session()
    try:
        row = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
        assert row.eligibility in (None, "open")  # unset reads as Anyone signed in
        states = sorted(
            session.scalars(select(Application.state).where(Application.exercise_id == row.id))
        )
    finally:
        session.close()
    assert workflow.form_state(exercise_or_404(made.public_id)) == "Open"
    assert states == ["draft"] * 2 + ["submitted"] * 4
    state = panels_store.stored(made.public_id)
    assert state is not None and [p.name for p in state.panels] == ["Readers", "Mentors"]
    readers = {m.email for m, keys in state.roster if state.panels[0].key in keys}
    assert identity_settings.fake_auth_email in readers


def test_a_second_run_changes_nothing() -> None:
    first = _open_form()
    session = db.new_session()
    try:
        before = session.scalar(select(func.count()).select_from(Application))
    finally:
        session.close()
    again = _open_form()
    assert again.public_id == first.public_id and not again.made
    session = db.new_session()
    try:
        assert session.scalar(select(func.count()).select_from(Application)) == before
    finally:
        session.close()


def test_the_second_account_sees_its_application_and_the_open_form() -> None:
    made = _open_form()
    client = TestClient(host_with(("applydesk",))[0])
    client.cookies.set("cordware_fake_as", "alt")
    lobby = client.get("/applydesk/me").text
    assert local_seed.OPEN_FORM in lobby
    assert "Herb garden on the roof" in lobby
    assert client.get(f"/applydesk/me/exercises/{made.public_id}").status_code == 200


def test_refused_without_fake_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    with pytest.raises(local_seed.LocalSeedRefused):
        local_seed.seed_local()


def test_the_create_dossiers_scenario() -> None:
    from applydesk import candidates
    from applydesk.models import Dossier

    made = next(m for m in local_seed.seed_local() if m.name == local_seed.CREATE_DOSSIERS)
    assert made.made
    session = db.new_session()
    try:
        listed = candidates.listing(session, made.public_id)
        row = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
        minted = session.scalar(
            select(func.count()).select_from(Dossier).where(Dossier.exercise_id == row.id)
        )
        assert candidates.per_person(session, made.public_id) == 2
    finally:
        session.close()
    assert len(listed) == 10 and minted == 10
    holders = {c.email for c in listed}
    assert len(holders) == 5 and identity_settings.fake_auth_email in holders
    assert {c.title for c in listed if c.email == identity_settings.fake_auth_email} == {
        "Peer mentor · Semester 1",
        "Peer mentor · Semester 2",
    }
    state = panels_store.stored(made.public_id)
    assert state is not None and len(state.panels) == 2
    # Local Operator holds dossiers here, so /me says so.
    lobby = TestClient(host_with(("applydesk",))[0]).get("/applydesk/me").text
    shown = lobby[lobby.index(local_seed.CREATE_DOSSIERS) :]
    assert "A dossier is held for you" in shown[: shown.index("</p>")]


def test_a_half_built_scenario_is_refused_not_skipped() -> None:
    """Cold read: a run that failed part-way leaves the exercise; a re-run
    says so and points at --reset rather than passing it off as there."""
    owner = local_seed.owner()
    client = local_seed._client()  # pyright: ignore[reportPrivateUsage]  -- the seed's own
    local_seed._make(client, local_seed.OPEN_FORM)  # pyright: ignore[reportPrivateUsage]  -- as a failed run leaves it
    assert owner.id
    with pytest.raises(local_seed.LocalSeedRefused, match="--reset"):
        local_seed.seed_local()


def test_the_second_account_is_a_plain_applicant() -> None:
    """Cold read: Divya Petrova applies, sits on no panel and holds no
    dossier."""
    from applydesk import candidates

    made = {m.name: m.public_id for m in local_seed.seed_local()}
    for public_id in made.values():
        state = panels_store.stored(public_id)
        assert state is not None
        assert "divya.petrova@example.edu" not in {m.email for m, _ in state.roster}
    session = db.new_session()
    try:
        held = candidates.listing(session, made[local_seed.CREATE_DOSSIERS])
    finally:
        session.close()
    assert "divya.petrova@example.edu" not in {c.email for c in held}


def test_six_applications_without_a_second_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_alt_email", "")
    made = _open_form()
    session = db.new_session()
    try:
        row = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
        n = session.scalar(
            select(func.count()).select_from(Application).where(Application.exercise_id == row.id)
        )
    finally:
        session.close()
    assert n == local_seed.APPLICANTS
    assert not _open_form().made  # and a re-run finds it complete


def test_the_second_account_sits_on_no_panel() -> None:
    """Codex on #4279: the plain applicant is on neither panel, which keep
    their sizes (Readers: Local Operator and three; Mentors: four)."""
    made = _open_form()
    state = panels_store.stored(made.public_id)
    assert state is not None
    assert "divya.petrova@example.edu" not in {m.email for m, _ in state.roster}
    sizes = sorted(sum(1 for _, keys in state.roster if p.key in keys) for p in state.panels)
    assert sizes == [4, 4]


def test_the_second_account_holds_no_dossier() -> None:
    """The cold read: the plain applicant holds no Create dossiers entry."""
    from applydesk import candidates

    made = next(m for m in local_seed.seed_local() if m.name == local_seed.CREATE_DOSSIERS)
    session = db.new_session()
    try:
        held = candidates.listing(session, made.public_id)
    finally:
        session.close()
    assert "divya.petrova@example.edu" not in {c.email for c in held}


def test_the_second_account_s_application_is_its_own_if_it_signed_in_first() -> None:
    """Codex on #4279: Divya Petrova signing in before the seed runs still
    finds her application on /me, not on a pending duplicate."""
    client = TestClient(host_with(("applydesk",))[0])
    client.cookies.set("cordware_fake_as", "alt")
    assert client.get("/applydesk/me").status_code == 200  # signs in first
    _open_form()
    assert "Herb garden on the roof" in client.get("/applydesk/me").text


def test_the_create_dossiers_scenario_runs_once() -> None:
    first = {m.name: m for m in local_seed.seed_local()}
    again = {m.name: m for m in local_seed.seed_local()}
    made = again[local_seed.CREATE_DOSSIERS]
    assert not made.made and made.public_id == first[local_seed.CREATE_DOSSIERS].public_id
    assert local_seed._count(made.public_id, local_seed.Candidate) == 10  # pyright: ignore[reportPrivateUsage]  -- the seed's own


def test_a_comma_in_the_operator_s_name_survives_the_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex on #4280: Create dossiers' CSV quotes a configured name with a
    comma, so Local Operator still holds two dossiers."""
    from applydesk import candidates

    monkeypatch.setattr(identity_settings, "fake_auth_name", "Operator, Local")
    made = next(m for m in local_seed.seed_local() if m.name == local_seed.CREATE_DOSSIERS)
    session = db.new_session()
    try:
        listed = candidates.listing(session, made.public_id)
    finally:
        session.close()
    assert len(listed) == 10
    assert sum(1 for c in listed if c.email == identity_settings.fake_auth_email) == 2


def test_the_dossiers_page_heads_its_rows_with_create_dossiers_stage() -> None:
    """Author, 2026-11-28: dossiers created by hand follow their stage's
    name and dates, as a form's applications do; "From elsewhere" is only
    for rows no stage made. A bound person's address is a pill."""
    import re

    made = next(m for m in local_seed.seed_local() if m.name == local_seed.CREATE_DOSSIERS)
    text = (
        TestClient(host_with(("applydesk",))[0])
        .get(f"/applydesk/operator/exercises/{made.public_id}/dossiers")
        .text
    )
    assert "From elsewhere" not in text
    head = re.search(
        r'<th class="ap-first" colspan="\d+"><b>([^<]+)</b><span class="ap-when">([^<]+)<', text
    )
    assert head is not None and head.groups() == ("Nominations", "Dates not set")
    me = identity_settings.fake_auth_email
    pills = re.findall(r'<span class="pl-addr" data-verified[^>]*>([^<]+)</span>', text)
    assert pills and set(pills) == {me}  # Local Operator is bound; the rest are pending
