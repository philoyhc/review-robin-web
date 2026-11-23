"""The form's moves, Home's next step (ruling 76, segment AD2C rung 9),
and a published stage's locks on a Process save (ruling 35): the form
opens once the exercise is published and only moves forward, each move
audited; a published stage keeps its name and dates until reverted, and
the revert is audited."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, process_store, stages, workflow
from applydesk.lookups import exercise_or_404
from applydesk.models import AuditEvent
from applydesk.models import Stage as StageRow
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
        reverted = (
            replace(stored.stages[0], name="Renamed", status="Draft", revert_reason="Wrong name"),
            *stored.stages[1:],
        )
        process_store.save(session, DONE, reverted, 1, None)
        session.commit()
    finally:
        session.close()
    assert _events("exercise.stage_reverted") == 1
    session = db.new_session()
    try:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "exercise.stage_reverted")
        )
        assert event is not None and event.detail["reason"] == "Wrong name"
    finally:
        session.close()


def _published() -> tuple[stages.Stage, ...]:
    built = tuple(replace(st, status="Published") for st in stages.plan_of(DONE).stages)
    session = db.new_session()
    try:
        process_store.save(session, DONE, built, 0, None)
        session.commit()
        stored = process_store.load(session, DONE)
        assert stored is not None
        return stored.stages
    finally:
        session.close()


def test_a_published_stage_s_end_is_extended() -> None:
    """The cold read on rungs 7-10: its end stays editable (ruling 35), an
    extension keeping it open; its start, and who sees it, do not."""
    stored = _published()
    first = stored[0]
    assert first.when is not None
    later = replace(first.when, end=first.when.end + timedelta(days=7))
    session = db.new_session()
    try:
        process_store.save(session, DONE, (replace(first, when=later), *stored[1:]), 1, None)
        session.commit()
        for change in (
            replace(first, when=replace(later, start=later.start - timedelta(days=1))),
            replace(first, when=later, shown=not first.shown),
        ):
            with pytest.raises(Refused) as locked:
                process_store.save(session, DONE, (change, *stored[1:]), 2, None)
            assert locked.value.key == "published"
            session.rollback()
    finally:
        session.close()


def test_nothing_is_added_to_a_published_stage() -> None:
    """The page disables a published stage's adds; a save refuses them too."""
    stored = _published()
    # Interviews' gate moved into Review, both published.
    review, interviews = stored[1], stored[2]
    moved = interviews.columns[0]
    assert isinstance(moved, stages.Gate)
    changed = list(stored)
    changed[1] = replace(review, columns=(*review.columns[:-1], moved, review.columns[-1]))
    changed[2] = replace(interviews, columns=interviews.columns[1:])
    session = db.new_session()
    try:
        with pytest.raises(Refused) as locked:
            process_store.save(session, DONE, tuple(changed), 1, None)
        assert locked.value.key == "published" and "add to it" in str(locked.value)
    finally:
        session.close()


def test_the_form_keeps_its_state_when_it_moves_stage() -> None:
    """The cold read on rungs 7-10: a closed form moved to another stage
    stays closed, rather than reseeded open from the sample."""
    client = _client()
    client.post(f"{LOBBY}/{OPEN}/form/move", data={"to": "closed"})
    session = db.new_session()
    try:
        stored = process_store.load(session, OPEN)
        assert stored is not None
        (first,) = stored.stages
        # The form moved on to a new draft stage after the published one.
        later = replace(first, key="", name="Next", status="Draft", columns=())
        moved = (replace(first, form=False, form_when=None), later)
        process_store.save(session, OPEN, moved, stored.revision, None)
        session.commit()
        assert process_store.form_state(session, OPEN) == "closed"
        holder = session.scalar(
            select(StageRow).where(StageRow.holds_form.is_(True), StageRow.retired_at.is_(None))
        )
        assert holder is not None and holder.form_closed_at is not None  # moved with it
    finally:
        session.close()


def test_a_first_save_refused_says_so_on_home(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_: object, **__: object) -> int:
        raise Refused("A rule reads amiss.")

    monkeypatch.setattr(process_store, "save", refuse)
    moved = _client().post(f"{LOBBY}/{OPEN}/form/move", data={"to": "closed"})
    assert "form_said=unsaved" in moved.headers["location"]


def test_a_draft_made_published_by_its_stages_opens_its_form() -> None:
    """Codex on #4161: an exercise made as a draft is published by
    publishing a stage; its form then opens, though the sample's stored
    state still says Draft."""
    built = stages.plan_of(DRAFT).stages
    session = db.new_session()
    try:
        published = (replace(built[0], status="Published"), *built[1:])
        process_store.save(session, DRAFT, published, 0, None)
        session.commit()
    finally:
        session.close()
    exercise = exercise_or_404(DRAFT)
    assert exercise.state == "Draft"  # the sample's own, unchanged
    action = workflow.form_action(exercise)
    assert action is not None and action[1:] == ("open", "")
    moved = _client().post(f"{LOBBY}/{DRAFT}/form/move", data={"to": "open"})
    assert "form_said=open" in moved.headers["location"]
    assert workflow.form_state(exercise_or_404(DRAFT)) == "Open"
