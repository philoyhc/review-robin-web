"""The timeline checked as a whole (segment AD2K, ruling 83,
`applydesk/timeline_checks.py`): its errors keep the first stage from
publishing; errors and warnings show on Process, as saved, and on Home."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from applydesk import locks, sample_data, stages, timeline_checks
from applydesk.stages import Gate, GateResult, Outcome, Plan, Stage
from applydesk.tests._host import host_with
from applydesk.timeline_checks import (
    NO_ENTRIES,
    NO_FIRST_ITEM,
    NO_INVITEES,
    NO_LAST_OUTCOME,
    POPULATE_AFTER_FORM,
)

pytestmark = pytest.mark.usefixtures("applydesk_db")

LOBBY = "/applydesk/operator/exercises"
_GATE = Gate("g1", 1, "Read", "RRW", (GateResult("r1", "Score", stages.Field("integer"), "mean"),))
_OUT = Outcome("o1", 1, "Decision", ("Yes", "No"), None, "", (("g1.r1", 1.0),))


def _plan(*built: Stage) -> Plan:
    return Plan(built, (), "x")


def test_the_first_item_is_a_form_or_populate_dossiers() -> None:
    assert timeline_checks.check(_plan(Stage(1, "", None)), 0).errors == (NO_FIRST_ITEM,)
    assert timeline_checks.check(_plan(), 0).errors == (NO_FIRST_ITEM,)
    gate_first = _plan(Stage(1, "", None, (_GATE, _OUT)), Stage(2, "", None, form=True))
    assert timeline_checks.check(gate_first, 0).errors == (NO_FIRST_ITEM,)
    assert timeline_checks.check(_plan(Stage(1, "", None, form=True)), 0).errors == ()
    populated = _plan(Stage(1, "", None, candidates=True), Stage(2, "", None, (_GATE, _OUT)))
    assert timeline_checks.check(populated, 3) == timeline_checks.Checked((), ())


def test_one_populating_item_in_order() -> None:
    form_then = _plan(Stage(1, "", None, form=True), Stage(2, "", None, candidates=True))
    assert timeline_checks.check(form_then, 1).errors == (POPULATE_AFTER_FORM,)
    then_form = _plan(Stage(1, "", None, candidates=True), Stage(2, "", None, form=True))
    # A Form after Create dossiers writes to the dossiers it made
    # (ruling 83 as amended, author 2026-11-27).
    assert timeline_checks.check(then_form, 1).errors == ()
    # One stage holding both is the Invitation only roster, until AD4.
    both = _plan(Stage(1, "", None, form=True, candidates=True))
    assert timeline_checks.check(both, 1).errors == ()


def test_warnings_publish_anyway() -> None:
    empty = _plan(Stage(1, "", None, candidates=True), Stage(2, "", None, (_GATE,)))
    assert timeline_checks.check(empty, 0) == timeline_checks.Checked(
        (), (NO_ENTRIES, NO_LAST_OUTCOME)
    )


def test_an_empty_invite_list_is_a_warning() -> None:
    form = _plan(Stage(1, "", None, form=True))
    assert timeline_checks.check(form, 0, 0) == timeline_checks.Checked((), (NO_INVITEES,))
    assert timeline_checks.check(form, 0, 2).warnings == ()
    assert timeline_checks.check(form, 0, None).warnings == ()  # Anyone signed in
    # After Create dossiers the Form invites from the dossiers: no list.
    led = _plan(Stage(1, "", None, candidates=True), Stage(2, "", None, form=True))
    assert NO_INVITEES not in timeline_checks.check(led, 1, 0).warnings


def test_the_samples_check_clean() -> None:
    for e in sample_data.EXERCISES:
        found = timeline_checks.of(e.public_id)
        assert found.errors == (), (e.public_id, found)


def test_a_new_exercise_is_blocked_and_process_says_why() -> None:
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage

    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)
    made = _create(client)
    exercise = sample_data.exercise(made)
    assert exercise is not None
    first = stages.plan_of(made).stages[0]
    assert NO_FIRST_ITEM in locks.publish_problems(exercise, first)
    page = client.get(f"{LOBBY}/{made}/process").text
    assert "data-pc-errors" in page and NO_FIRST_ITEM in page
    saved = _post_process(client, made, {"stages": [_stage("People", candidates=True)]})
    assert saved.status_code == 200, saved.text
    first = stages.plan_of(made).stages[0]
    assert NO_FIRST_ITEM not in locks.publish_problems(exercise, first)
    page = client.get(f"{LOBBY}/{made}/process").text
    assert "data-pc-errors" not in page and NO_ENTRIES in page
    home = client.get(f"{LOBBY}/{made}").text
    assert "data-tl-warnings" in home and NO_ENTRIES in home
    assert "Application form" not in home  # no form, so no questions owed
