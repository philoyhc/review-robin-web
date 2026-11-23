"""The form's moves, Home's next step (ruling 76, segment AD2C rung 9),
and a published stage's locks on a Process save (ruling 35): the form
opens once the exercise is published and only moves forward, each move
audited; a published stage keeps its name and dates until reverted, and
the revert is audited."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, process_store, stages, workflow
from applydesk.lookups import exercise_or_404
from applydesk.models import AuditEvent
from applydesk.process_store import Refused
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"
DRAFT = "c4xh2ndv6s"  # a draft exercise with a form
OPEN = "r6tm4kq9wz"  # published, its form open
DONE = "wa9juxbc2t"  # published, its form closed


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _events(kind: str) -> int:
    session = db.new_session()
    try:
        return len(list(session.scalars(select(AuditEvent).where(AuditEvent.event_type == kind))))
    finally:
        session.close()


def test_home_offers_the_form_s_next_move() -> None:
    client = _client()
    draft = client.get(f"{LOBBY}/{DRAFT}").text
    assert ">Open form</button>" in draft and "data-tl-form disabled" in draft
    assert "A draft&#39;s form opens once the exercise is published." in draft
    opened = client.get(f"{LOBBY}/{OPEN}").text
    assert ">Close form</button>" in opened and "data-tl-form disabled" not in opened
    assert 'name="to" value="closed"' in opened
    assert "data-tl-form" not in client.get(f"{LOBBY}/{DONE}").text  # closed: nothing to do


def test_closing_the_form_moves_it_forward_once_and_audits_it() -> None:
    client = _client()
    moved = client.post(f"{LOBBY}/{OPEN}/form/move", data={"to": "closed"})
    assert moved.status_code == 303 and "form_said=closed" in moved.headers["location"]
    assert workflow.form_state(exercise_or_404(OPEN)) == "Closed"
    assert _events("exercise.form_closed") == 1
    # The timeline was recorded first, as Process would save it.
    assert stages.plan_of(OPEN).stages[0].key
    again = client.post(f"{LOBBY}/{OPEN}/form/move", data={"to": "closed"})
    assert "form_said=form_state" in again.headers["location"]
    home = client.get(again.headers["location"].removeprefix("http://testserver")).text
    assert "The form has moved since this page opened" in home
    assert _events("exercise.form_closed") == 1


def test_a_draft_s_form_does_not_open() -> None:
    session = db.new_session()
    try:
        with pytest.raises(Refused) as draft:
            process_store.move_form(session, DRAFT, "open", False, None)
        assert draft.value.key == "draft"
    finally:
        session.close()
    refused = _client().post(f"{LOBBY}/{DRAFT}/form/move", data={"to": "open"})
    assert "form_said=draft" in refused.headers["location"]
    assert _client().post(f"{LOBBY}/{DRAFT}/form/move", data={"to": "sideways"}).status_code == 400


def test_a_published_stage_keeps_its_name_and_dates_until_reverted() -> None:
    built = tuple(replace(st, status="Published") for st in stages.plan_of(DONE).stages)
    session = db.new_session()
    try:
        process_store.save(session, DONE, built, 0, None)
        session.commit()
        stored = process_store.load(session, DONE)
        assert stored is not None
        renamed = (replace(stored.stages[0], name="Renamed"), *stored.stages[1:])
        with pytest.raises(Refused) as locked:
            process_store.save(session, DONE, renamed, 1, None)
        assert locked.value.key == "published" and "revert it to draft" in str(locked.value)
        session.rollback()
        # Reverted to draft, the same change saves, and the revert is audited.
        reverted = (replace(stored.stages[0], name="Renamed", status="Draft"), *stored.stages[1:])
        process_store.save(session, DONE, reverted, 1, None)
        session.commit()
    finally:
        session.close()
    assert _events("exercise.stage_reverted") == 1
